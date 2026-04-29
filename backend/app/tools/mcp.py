from __future__ import annotations

from typing import Any

from app.models.schemas import Paper, ToolDescriptor
from app.tools.arxiv import ArxivSearchTool


class MCPToolRegistry:
    """Lightweight in-process MCP-style registry for tool descriptors and calls."""

    def __init__(self, arxiv_tool: ArxivSearchTool) -> None:
        self.arxiv_tool = arxiv_tool

    def list_tools(self) -> list[ToolDescriptor]:
        return [
            ToolDescriptor(
                name="arxiv_search",
                description="Search arXiv papers and return title, authors, abstract and PDF URL.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "arXiv search query"},
                        "max_results": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[Paper]:
        if name != "arxiv_search":
            raise ValueError(f"Unknown MCP tool: {name}")
        return await self.arxiv_tool.search(
            query=str(arguments.get("query", "")),
            max_results=int(arguments.get("max_results", 5)),
        )

