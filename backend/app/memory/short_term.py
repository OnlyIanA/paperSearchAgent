from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MemoryMessage:
    role: str
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)


class ShortTermMemory:
    """In-memory conversation buffer keyed by session id."""

    def __init__(self, window: int = 16) -> None:
        self.window = window
        self._buffers: dict[str, deque[MemoryMessage]] = defaultdict(
            lambda: deque(maxlen=self.window)
        )

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self._buffers[session_id].append(MemoryMessage(role=role, content=content))

    def get_messages(self, session_id: str, limit: int | None = None) -> list[MemoryMessage]:
        messages = list(self._buffers.get(session_id, []))
        if limit is None:
            return messages
        return messages[-limit:]

    def render_context(self, session_id: str, limit: int | None = None) -> str:
        lines: list[str] = []
        for message in self.get_messages(session_id, limit=limit):
            lines.append(f"{message.role}: {message.content}")
        return "\n".join(lines)

