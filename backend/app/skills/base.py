from __future__ import annotations

from typing import Protocol


class Skill(Protocol):
    name: str
    description: str

    async def run(self, text: str) -> str:
        ...

