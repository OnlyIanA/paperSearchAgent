from __future__ import annotations

from app.core.config import get_settings
from app.tools.arxiv import ArxivSearchTool

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("请先安装 mcp 包：pip install mcp") from exc


settings = get_settings()
arxiv_tool = ArxivSearchTool(settings)
mcp = FastMCP("paper-search-agent")


@mcp.tool()
async def arxiv_search(query: str, max_results: int = 5) -> list[dict[str, object]]:
    """Search arXiv and return title, authors, abstract and PDF link."""

    papers = await arxiv_tool.search(query=query, max_results=max_results)
    return [paper.model_dump() for paper in papers]


if __name__ == "__main__":
    mcp.run(transport="stdio")

