from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class ArxivSearchInput(BaseModel):
    query: str = Field(..., description="Search query for arXiv.")
    max_results: int = Field(default=5, ge=1, le=10)


class SummarizePaperInput(BaseModel):
    paper_text: str = Field(..., description="Paper title, abstract or full paper text.")


class RetrieveMemoryInput(BaseModel):
    query: str = Field(..., description="Semantic memory retrieval query.")
    top_k: int = Field(default=5, ge=1, le=12)


def build_langchain_tools(
    *,
    arxiv_search: Callable[[str, int], Awaitable[Any]],
    summarize_paper: Callable[[str], Awaitable[str]],
    retrieve_memory: Callable[[str, int], Awaitable[Any]],
) -> list[StructuredTool]:
    """Expose project capabilities as LangChain structured tools."""

    async def _arxiv_search(query: str, max_results: int = 5) -> Any:
        return await arxiv_search(query, max_results)

    async def _summarize_paper(paper_text: str) -> str:
        return await summarize_paper(paper_text)

    async def _retrieve_memory(query: str, top_k: int = 5) -> Any:
        return await retrieve_memory(query, top_k)

    return [
        StructuredTool.from_function(
            coroutine=_arxiv_search,
            name="arxiv_search",
            description="Search arXiv papers by query.",
            args_schema=ArxivSearchInput,
        ),
        StructuredTool.from_function(
            coroutine=_summarize_paper,
            name="summarize_paper",
            description="Summarize a paper from abstract or paper text.",
            args_schema=SummarizePaperInput,
        ),
        StructuredTool.from_function(
            coroutine=_retrieve_memory,
            name="retrieve_memory",
            description="Retrieve relevant long-term memory and RAG chunks.",
            args_schema=RetrieveMemoryInput,
        ),
    ]

