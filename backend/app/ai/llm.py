"""LLM client abstraction. Only this module talks to the OpenAI SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from app.core.errors import AIUnavailable, ServiceUnavailableError
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str | None = None
    raw_tool_calls: list[dict[str, Any]] = field(default_factory=list)  # for echoing back to the model

    def assistant_message(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.raw_tool_calls:
            msg["tool_calls"] = self.raw_tool_calls
        return msg


class LLMClient(Protocol):
    model: str

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_model: type[BaseModel] | None = None,
        tool_choice: str | None = None,
        temperature: float = 0.3,
    ) -> LLMResponse: ...


def _strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic JSON schema adjusted for OpenAI strict structured outputs."""
    schema = model.model_json_schema()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for key in ("default",):
                node.pop(key, None)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


class OpenAIClient:
    """Chat-completions client. Gemini and Groq use the same request shape."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        base_url: str | None = None,
        provider: str = "openai",
    ):
        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self.model = model
        self.provider = provider

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_model: type[BaseModel] | None = None,
        tool_choice: str | None = None,
        temperature: float = 0.3,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        if response_model is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": _strict_schema(response_model),
                    "strict": True,
                },
            }
        try:
            completion = await self._client.chat.completions.create(**kwargs)
        except RateLimitError as exc:
            raise ServiceUnavailableError("The AI service is rate limited. Try again shortly.") from exc
        except APIConnectionError as exc:
            raise ServiceUnavailableError("Could not reach the AI service.") from exc
        except APIStatusError as exc:
            log.warning("llm.status_error", provider=self.provider, status=exc.status_code, message=str(exc))
            if exc.status_code in (401, 403):
                raise AIUnavailable(f"The {self.provider} API key is invalid.") from exc
            raise ServiceUnavailableError("The AI service returned an error.") from exc

        choice = completion.choices[0]
        message = choice.message
        tool_calls: list[ToolCall] = []
        raw_calls: list[dict[str, Any]] = []
        for tc in message.tool_calls or []:
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            try:
                args = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": fn.arguments}
            tool_calls.append(ToolCall(id=tc.id, name=fn.name, arguments=args))
            raw_calls.append(echo_tool_call(tc))
        return LLMResponse(
            content=message.content, tool_calls=tool_calls, model=completion.model, raw_tool_calls=raw_calls
        )


def echo_tool_call(tool_call: Any) -> dict[str, Any]:
    """Replay a tool call, including Gemini's thought signature when one was returned.

    Gemini 3 rejects the next turn if the first function call of a step is missing
    extra_content.google.thought_signature. The OpenAI client keeps that field, so
    it has to be copied onto the message we send back.
    """
    function = tool_call.function
    payload: dict[str, Any] = {
        "id": tool_call.id,
        "type": getattr(tool_call, "type", None) or "function",
        "function": {"name": function.name, "arguments": function.arguments or "{}"},
    }
    dumped = tool_call.model_dump() if hasattr(tool_call, "model_dump") else {}
    extra = dumped.get("extra_content") if isinstance(dumped, dict) else None
    if not extra:
        extra = getattr(tool_call, "extra_content", None)
    if isinstance(extra, dict) and extra:
        payload["extra_content"] = extra
    return payload


def build_llm(settings) -> OpenAIClient | None:
    """Prefer a free tool-calling model. OpenAI is used only when no free key is set."""
    if settings.gemini_api_key:
        return OpenAIClient(
            settings.gemini_api_key,
            settings.gemini_model,
            base_url=settings.gemini_base_url,
            provider="gemini",
        )
    if settings.groq_api_key:
        return OpenAIClient(
            settings.groq_api_key,
            settings.groq_model,
            base_url=settings.groq_base_url,
            provider="groq",
        )
    if settings.openai_api_key:
        return OpenAIClient(settings.openai_api_key, settings.openai_model, provider="openai")
    return None
