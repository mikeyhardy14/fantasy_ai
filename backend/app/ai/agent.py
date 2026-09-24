"""Generic tool-calling loop. Independent of any fantasy provider."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai.llm import LLMClient, LLMResponse
from app.ai.tools.base import ToolContext, ToolRegistry
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class AgentResult:
    content: str | None
    structured: BaseModel | None
    tools_used: list[str] = field(default_factory=list)
    model: str | None = None
    rounds: int = 0


class Agent:
    def __init__(self, llm: LLMClient, registry: ToolRegistry, max_rounds: int = 8):
        self.llm = llm
        self.registry = registry
        self.max_rounds = max_rounds

    async def run(
        self,
        messages: list[dict[str, Any]],
        ctx: ToolContext,
        *,
        response_model: type[BaseModel] | None = None,
        temperature: float = 0.3,
    ) -> AgentResult:
        history = list(messages)
        specs = self.registry.specs()
        rounds = 0
        last: LLMResponse | None = None

        while rounds < self.max_rounds:
            rounds += 1
            last = await self.llm.complete(history, tools=specs, temperature=temperature)
            if not last.tool_calls:
                break
            history.append(last.assistant_message())
            results = await asyncio.gather(
                *(self.registry.execute(tc.name, tc.arguments, ctx) for tc in last.tool_calls)
            )
            for tc, result in zip(last.tool_calls, results, strict=True):
                log.info("ai.tool_call", tool=tc.name, args=tc.arguments, size=len(result))
                history.append({"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": result})
        else:
            # Ran out of rounds while still requesting tools: force a final answer.
            history.append(
                {
                    "role": "user",
                    "content": "Stop calling tools and answer now with the information gathered. Note any gaps.",
                }
            )
            last = await self.llm.complete(history, temperature=temperature)

        assert last is not None
        if response_model is None:
            return AgentResult(content=last.content, structured=None, tools_used=list(ctx.tools_used), model=last.model, rounds=rounds)

        # Structured final answer: one extra call without tools so the schema is enforced.
        if last.content:
            history.append({"role": "assistant", "content": last.content})
        history.append(
            {
                "role": "user",
                "content": "Now return the final answer strictly in the requested JSON schema, using only facts from the tool results above.",
            }
        )
        structured = await self._structured(history, response_model, temperature)
        return AgentResult(
            content=last.content, structured=structured, tools_used=list(ctx.tools_used), model=last.model, rounds=rounds
        )

    async def _structured(self, history: list[dict[str, Any]], model: type[BaseModel], temperature: float) -> BaseModel:
        for attempt in range(2):
            resp = await self.llm.complete(history, response_model=model, temperature=temperature)
            try:
                return model.model_validate_json(resp.content or "")
            except ValidationError as exc:
                log.warning("ai.structured_invalid", attempt=attempt, errors=str(exc)[:500])
                history.append({"role": "assistant", "content": resp.content or ""})
                history.append(
                    {"role": "user", "content": f"That JSON was invalid: {str(exc)[:800]}. Return corrected JSON only."}
                )
        raise ServiceUnavailableError("The AI returned an invalid structured response. Please try again.")
