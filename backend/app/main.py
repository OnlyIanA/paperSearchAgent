from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.agent import ResearchAgent
from app.core.config import get_settings
from app.models.schemas import ChatRequest


settings = get_settings()
agent = ResearchAgent(settings)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "ok": True,
        "app": settings.app_name,
        "env": settings.app_env,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "deepseek_model": settings.deepseek_model,
        "deepseek_base_url": settings.deepseek_base_url,
    }


@app.get(f"{settings.api_prefix}/tools")
async def list_tools() -> dict[str, object]:
    return {
        "mcp_tools": [tool.model_dump() for tool in agent.mcp_registry.list_tools()],
        "langchain_tools": [
            {"name": tool.name, "description": tool.description}
            for tool in agent.langchain_tools
        ],
        "skills": [
            {
                "name": agent.paper_summary_skill.name,
                "description": agent.paper_summary_skill.description,
            },
            {
                "name": agent.conversation_summary_skill.name,
                "description": agent.conversation_summary_skill.description,
            },
        ],
    }


@app.post(f"{settings.api_prefix}/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def generate() -> AsyncIterator[str]:
        try:
            async for event in agent.stream(request):
                yield _sse(event)
        except Exception as exc:
            yield _sse({"type": "error", "content": f"服务端异常：{exc}"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(f"{settings.api_prefix}/chat")
async def chat_once(request: ChatRequest) -> dict[str, object]:
    events: list[dict[str, object]] = []
    answer_parts: list[str] = []
    async for event in agent.stream(request):
        events.append(event)
        if event.get("type") == "token":
            answer_parts.append(str(event.get("content", "")))
    return {"answer": "".join(answer_parts), "events": events}
