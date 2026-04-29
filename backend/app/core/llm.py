from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.core.config import Settings


def has_deepseek_key(settings: Settings) -> bool:
    key = (settings.deepseek_api_key or "").strip()
    return bool(key and not key.startswith("sk-your-"))


def build_deepseek_client(settings: Settings, *, temperature: float = 0.2) -> DeepSeekClient:
    return DeepSeekClient(settings=settings, temperature=temperature)


class DeepSeekClient:
    """Minimal async client for DeepSeek Chat Completions."""

    def __init__(self, settings: Settings, *, temperature: float = 0.2) -> None:
        self.settings = settings
        self.temperature = temperature

    async def complete(self, messages: list[BaseMessage]) -> str:
        payload = self._payload(messages, stream=False)
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(self._url, headers=self._headers, json=payload)
            self._raise_for_status(response)
            data = response.json()
        return str(data["choices"][0]["message"]["content"]).strip()

    async def stream(self, messages: list[BaseMessage]) -> AsyncIterator[str]:
        payload = self._payload(messages, stream=True)
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                self._url,
                headers=self._headers,
                json=payload,
                timeout=self.settings.request_timeout_seconds,
            ) as response:
                self._raise_for_status(response)
                async for line in response.aiter_lines():
                    token = self._parse_stream_line(line)
                    if token:
                        yield token

    @property
    def _url(self) -> str:
        return f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions"

    @property
    def _headers(self) -> dict[str, str]:
        if not self.settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法调用 DeepSeek 模型。")
        return {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:500].strip()
            raise RuntimeError(
                "DeepSeek API 调用失败："
                f"HTTP {response.status_code}。请检查 DEEPSEEK_API_KEY、"
                f"DEEPSEEK_MODEL 和账号余额/权限。{detail}"
            ) from exc

    def _payload(self, messages: list[BaseMessage], *, stream: bool) -> dict[str, Any]:
        return {
            "model": self.settings.deepseek_model,
            "messages": [self._message_to_payload(message) for message in messages],
            "temperature": self.temperature,
            "stream": stream,
        }

    def _message_to_payload(self, message: BaseMessage) -> dict[str, str]:
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        else:
            role = getattr(message, "type", "user")
        return {"role": role, "content": str(message.content)}

    def _parse_stream_line(self, line: str) -> str:
        line = line.strip()
        if not line or not line.startswith("data:"):
            return ""
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            return ""
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            return ""
        choices = payload.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        return str(delta.get("content") or "")
