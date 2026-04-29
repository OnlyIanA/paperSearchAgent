from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Paper(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str
    pdf_url: str
    source_url: str
    published: str | None = None
    updated: str | None = None
    categories: list[str] = Field(default_factory=list)


class PaperSummary(BaseModel):
    arxiv_id: str
    title: str
    summary: str


class MemoryHit(BaseModel):
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=12)
    max_results: int = Field(default=5, ge=1, le=10)
    search: bool | None = None


class ChatEvent(BaseModel):
    type: Literal[
        "session",
        "status",
        "memory",
        "papers",
        "summary",
        "token",
        "warning",
        "error",
        "done",
    ]
    content: str | None = None
    session_id: str | None = None
    papers: list[Paper] | None = None
    summaries: list[PaperSummary] | None = None
    memories: list[MemoryHit] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ToolDescriptor(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]

