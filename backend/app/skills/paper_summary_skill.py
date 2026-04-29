from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.llm import build_deepseek_client, has_deepseek_key


class PaperSummarySkill:
    name = "paper_summary_skill"
    description = "Summarize research papers into concise Chinese notes."

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, text: str) -> str:
        paper_text = text.strip()[: self.settings.max_paper_chars]
        if not paper_text:
            return "未提供可总结的论文内容。"
        if not has_deepseek_key(self.settings):
            return self._fallback_summary(paper_text)

        llm = build_deepseek_client(self.settings, temperature=0.15)
        messages = [
            SystemMessage(
                content=(
                    "你是资深 AI 研究员。请用中文总结论文，保持准确、紧凑，"
                    "覆盖研究问题、方法、关键贡献、可能局限和适合追问的方向。"
                )
            ),
            HumanMessage(content=f"请总结下面的论文信息：\n\n{paper_text}"),
        ]
        try:
            return await llm.complete(messages)
        except Exception as exc:
            return (
                f"DeepSeek 调用失败：{exc}\n\n"
                f"{self._fallback_summary(paper_text)}"
            )

    def _fallback_summary(self, text: str) -> str:
        snippet = text[:900].strip()
        if len(text) > 900:
            snippet += "..."
        return (
            "DEEPSEEK_API_KEY 未配置，当前使用抽取式摘要。"
            f"\n\n核心内容：{snippet}"
        )
