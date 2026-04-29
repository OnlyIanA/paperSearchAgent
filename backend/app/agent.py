from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings, get_settings
from app.core.llm import build_deepseek_client, has_deepseek_key
from app.memory.short_term import ShortTermMemory
from app.memory.sqlite_store import SQLiteMemoryStore
from app.models.schemas import ChatRequest, MemoryHit, Paper, PaperSummary
from app.rag.vector_store import ChromaRAGStore
from app.skills.conversation_summary_skill import ConversationSummarySkill
from app.skills.paper_summary_skill import PaperSummarySkill
from app.tools.arxiv import ArxivSearchTool
from app.tools.langchain_tools import build_langchain_tools
from app.tools.mcp import MCPToolRegistry


SEARCH_MARKERS = (
    "arxiv",
    "paper",
    "papers",
    "论文",
    "文献",
    "检索",
    "搜索",
    "找",
    "查找",
    "survey",
    "综述",
    "sota",
    "recent",
    "latest",
    "最新",
)

FOLLOW_UP_MARKERS = (
    "这篇",
    "上述",
    "上面",
    "刚才",
    "第一篇",
    "第二篇",
    "第三篇",
    "这些论文",
    "展开",
    "对比",
    "继续",
)


class ResearchAgent:
    """Tool-based research assistant with short-term memory, SQLite and Chroma RAG."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.short_term = ShortTermMemory(window=self.settings.short_term_window)
        self.long_term = SQLiteMemoryStore(self.settings.sqlite_file)
        self.vector_store = ChromaRAGStore(self.settings)
        self.arxiv_tool = ArxivSearchTool(self.settings)
        self.mcp_registry = MCPToolRegistry(self.arxiv_tool)
        self.paper_summary_skill = PaperSummarySkill(self.settings)
        self.conversation_summary_skill = ConversationSummarySkill(self.settings)
        self.langchain_tools = build_langchain_tools(
            arxiv_search=self._arxiv_search_tool,
            summarize_paper=self._summarize_paper_tool,
            retrieve_memory=self._retrieve_memory_tool,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[dict[str, object]]:
        session_id = request.session_id or str(uuid.uuid4())
        user_message = request.message.strip()
        self.short_term.add_message(session_id, "user", user_message)
        self.long_term.store_chat_log(session_id, "user", user_message)

        yield {"type": "session", "session_id": session_id}

        yield {"type": "status", "content": "正在检索长期记忆与向量库..."}
        memory_hits, memory_warning = await self._safe_retrieve_memory(
            user_message,
            top_k=request.top_k,
        )
        if memory_warning:
            yield {"type": "warning", "content": memory_warning}
        if memory_hits:
            yield {
                "type": "memory",
                "memories": [hit.model_dump() for hit in memory_hits],
                "content": f"找到 {len(memory_hits)} 条相关记忆。",
            }

        search_needed = (
            request.search
            if request.search is not None
            else self._should_search(user_message, memory_hits)
        )

        papers: list[Paper] = []
        summaries: list[PaperSummary] = []
        if search_needed:
            yield {"type": "status", "content": "正在通过 MCP 工具调用 arXiv..."}
            try:
                papers = await self.mcp_registry.call_tool(
                    "arxiv_search",
                    {"query": user_message, "max_results": request.max_results},
                )
            except Exception as exc:
                yield {"type": "error", "content": f"arXiv 检索失败：{exc}"}
                papers = []

            if papers:
                yield {
                    "type": "papers",
                    "papers": [paper.model_dump() for paper in papers],
                    "content": f"检索到 {len(papers)} 篇论文。",
                }
                async for summary_event in self._store_and_summarize_papers(
                    session_id=session_id,
                    papers=papers,
                ):
                    if summary_event.get("type") == "summary":
                        summaries.extend(
                            PaperSummary(**item)
                            for item in summary_event.get("summaries", [])
                        )
                    yield summary_event
            else:
                yield {"type": "warning", "content": "未检索到论文，将基于已有记忆回答。"}
        else:
            yield {"type": "status", "content": "本轮优先基于已有上下文和记忆回答。"}

        yield {"type": "status", "content": "正在生成回答..."}
        answer_parts: list[str] = []
        async for token in self._stream_final_answer(
            question=user_message,
            session_id=session_id,
            memory_hits=memory_hits,
            papers=papers,
            summaries=summaries,
        ):
            answer_parts.append(token)
            yield {"type": "token", "content": token}

        answer = "".join(answer_parts).strip()
        if answer:
            self.short_term.add_message(session_id, "assistant", answer)
            self.long_term.store_chat_log(session_id, "assistant", answer)
            await self._maybe_store_conversation_summary(session_id)

        yield {"type": "done", "session_id": session_id, "content": answer}

    async def _store_and_summarize_papers(
        self,
        *,
        session_id: str,
        papers: list[Paper],
    ) -> AsyncIterator[dict[str, object]]:
        for paper in papers:
            self.long_term.upsert_paper(paper)
            paper_text = self._paper_to_text(paper)
            yield {"type": "status", "content": f"正在总结：{paper.title}"}
            summary = await self.paper_summary_skill.run(paper_text)
            self.long_term.store_summary(
                arxiv_id=paper.arxiv_id,
                title=paper.title,
                summary=summary,
                skill_name=self.paper_summary_skill.name,
            )
            self.long_term.store_memory(
                content=summary,
                kind="paper_summary",
                session_id=session_id,
                metadata={"arxiv_id": paper.arxiv_id, "title": paper.title},
            )

            vector_warning = await self._safe_store_vectors(
                paper=paper,
                summary=summary,
                session_id=session_id,
            )
            if vector_warning:
                yield {"type": "warning", "content": vector_warning}

            yield {
                "type": "summary",
                "summaries": [
                    PaperSummary(
                        arxiv_id=paper.arxiv_id,
                        title=paper.title,
                        summary=summary,
                    ).model_dump()
                ],
            }

    async def _safe_store_vectors(
        self,
        *,
        paper: Paper,
        summary: str,
        session_id: str,
    ) -> str | None:
        try:
            await asyncio.to_thread(self.vector_store.upsert_paper, paper, summary)
            await asyncio.to_thread(
                self.vector_store.add_memory,
                summary,
                kind="paper_summary",
                session_id=session_id,
                metadata={"arxiv_id": paper.arxiv_id, "title": paper.title},
            )
            return None
        except RuntimeError as exc:
            return str(exc)
        except Exception as exc:
            return f"向量存储失败：{exc}"

    async def _safe_retrieve_memory(
        self,
        query: str,
        *,
        top_k: int,
    ) -> tuple[list[MemoryHit], str | None]:
        try:
            hits = await asyncio.to_thread(self.vector_store.retrieve, query, top_k=top_k)
            return hits, None
        except RuntimeError as exc:
            return [], str(exc)
        except Exception as exc:
            return [], f"长期记忆检索失败：{exc}"

    async def _stream_final_answer(
        self,
        *,
        question: str,
        session_id: str,
        memory_hits: list[MemoryHit],
        papers: list[Paper],
        summaries: list[PaperSummary],
    ) -> AsyncIterator[str]:
        if not has_deepseek_key(self.settings):
            fallback = self._fallback_answer(question, memory_hits, papers, summaries)
            for token in self._chunk_text(fallback):
                await asyncio.sleep(0.01)
                yield token
            return

        llm = build_deepseek_client(self.settings, temperature=0.2)
        short_context = self.short_term.render_context(session_id, limit=10)
        memory_context = "\n\n".join(
            f"[{index + 1}] score={hit.score:.3f} meta={hit.metadata}\n{hit.content}"
            for index, hit in enumerate(memory_hits)
        )
        paper_context = "\n\n".join(self._paper_to_text(paper) for paper in papers)
        summary_context = "\n\n".join(
            f"{item.title} ({item.arxiv_id})\n{item.summary}" for item in summaries
        )
        messages = [
            SystemMessage(
                content=(
                    "你是一个 AI 论文研究助手。必须用中文回答。"
                    "回答时先给直接结论，再列出相关论文、贡献和后续建议。"
                    "如果使用了论文，给出标题、arXiv ID 和 PDF 链接。"
                    "不要编造未提供的实验结果或论文细节。"
                )
            ),
            HumanMessage(
                content=(
                    f"用户问题：{question}\n\n"
                    f"短期对话上下文：\n{short_context or '无'}\n\n"
                    f"长期记忆/RAG 片段：\n{memory_context or '无'}\n\n"
                    f"本轮检索论文：\n{paper_context or '无'}\n\n"
                    f"论文技能摘要：\n{summary_context or '无'}"
                )
            ),
        ]
        try:
            async for content in llm.stream(messages):
                if content:
                    yield content
        except Exception as exc:
            fallback = self._fallback_answer(question, memory_hits, papers, summaries)
            error_text = (
                f"DeepSeek 调用失败：{exc}\n\n"
                "下面先给出不依赖模型 API 的本地结果，方便你继续排查：\n\n"
                f"{fallback}"
            )
            for token in self._chunk_text(error_text):
                await asyncio.sleep(0.01)
                yield token

    async def _maybe_store_conversation_summary(self, session_id: str) -> None:
        recent_messages = self.short_term.get_messages(session_id)
        if len(recent_messages) < self.settings.conversation_summary_threshold:
            return

        context = self.short_term.render_context(session_id)
        summary = await self.conversation_summary_skill.run(context)
        self.long_term.store_memory(
            content=summary,
            kind="conversation_summary",
            session_id=session_id,
            metadata={"skill": self.conversation_summary_skill.name},
        )
        try:
            await asyncio.to_thread(
                self.vector_store.add_memory,
                summary,
                kind="conversation_summary",
                session_id=session_id,
                metadata={"skill": self.conversation_summary_skill.name},
            )
        except Exception:
            pass

    def _should_search(self, message: str, memory_hits: list[MemoryHit]) -> bool:
        lower = message.lower()
        if memory_hits and any(marker in lower for marker in FOLLOW_UP_MARKERS):
            return False
        if any(marker in lower for marker in SEARCH_MARKERS):
            return True
        return not memory_hits

    def _fallback_answer(
        self,
        question: str,
        memory_hits: list[MemoryHit],
        papers: list[Paper],
        summaries: list[PaperSummary],
    ) -> str:
        lines = [
            "DEEPSEEK_API_KEY 未配置，所以当前返回规则生成的结果；配置后会启用 DeepSeek 模型和流式 LLM 回答。",
            "",
            f"你的问题：{question}",
        ]
        if papers:
            lines.extend(["", "检索到的论文："])
            for paper in papers:
                authors = ", ".join(paper.authors[:4])
                if len(paper.authors) > 4:
                    authors += " 等"
                lines.append(f"- {paper.title} ({paper.arxiv_id})")
                lines.append(f"  作者：{authors or '未知'}")
                lines.append(f"  PDF：{paper.pdf_url}")
        if summaries:
            lines.extend(["", "论文摘要："])
            for item in summaries:
                lines.append(f"- {item.title}: {item.summary[:700]}")
        if memory_hits:
            lines.extend(["", "相关长期记忆："])
            for hit in memory_hits[:3]:
                lines.append(f"- {hit.content[:300]}")
        return "\n".join(lines)

    def _chunk_text(self, text: str, size: int = 18) -> list[str]:
        return [text[index : index + size] for index in range(0, len(text), size)]

    def _paper_to_text(self, paper: Paper) -> str:
        return (
            f"标题：{paper.title}\n"
            f"arXiv ID：{paper.arxiv_id}\n"
            f"作者：{', '.join(paper.authors)}\n"
            f"分类：{', '.join(paper.categories)}\n"
            f"发布时间：{paper.published or '未知'}\n"
            f"PDF：{paper.pdf_url}\n"
            f"摘要：{paper.abstract}"
        )

    async def _arxiv_search_tool(self, query: str, max_results: int = 5) -> list[dict[str, object]]:
        papers = await self.mcp_registry.call_tool(
            "arxiv_search",
            {"query": query, "max_results": max_results},
        )
        return [paper.model_dump() for paper in papers]

    async def _summarize_paper_tool(self, paper_text: str) -> str:
        return await self.paper_summary_skill.run(paper_text)

    async def _retrieve_memory_tool(self, query: str, top_k: int = 5) -> list[dict[str, object]]:
        hits, _ = await self._safe_retrieve_memory(query, top_k=top_k)
        return [hit.model_dump() for hit in hits]
