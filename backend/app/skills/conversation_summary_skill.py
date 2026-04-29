from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.llm import build_deepseek_client, has_deepseek_key


class ConversationSummarySkill:
    name = "conversation_summary_skill"
    description = "Compress a conversation into long-term memory."

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, text: str) -> str:
        conversation = text.strip()
        if not conversation:
            return "空对话，无需总结。"
        if not has_deepseek_key(self.settings):
            return self._fallback_summary(conversation)

        llm = build_deepseek_client(self.settings, temperature=0.1)
        messages = [
            SystemMessage(
                content=(
                    "你负责维护研究助手的长期记忆。请用中文压缩对话，保留用户目标、"
                    "已检索论文、关键偏好、尚未解决的问题。"
                )
            ),
            HumanMessage(content=f"请压缩下面对话为长期记忆：\n\n{conversation}"),
        ]
        try:
            return await llm.complete(messages)
        except Exception as exc:
            return (
                f"DeepSeek 调用失败：{exc}\n\n"
                f"{self._fallback_summary(conversation)}"
            )

    def _fallback_summary(self, text: str) -> str:
        snippet = text[-1000:].strip()
        return f"对话摘要（抽取式）：{snippet}"
