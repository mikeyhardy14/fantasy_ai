"""Tool framework for LLM function calling.

A Tool is a name + description + Pydantic argument model + async handler.
Handlers receive a ToolContext that is bound to exactly one authorized league,
so tools cannot reach data the calling user does not own.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.intelligence.context import TeamContext
from app.models import League
from app.repositories import LeagueRepository
from app.services.league_context import LeagueContextService

log = get_logger(__name__)


class ToolContext:
    """Per-request state shared by all tool invocations."""

    def __init__(
        self,
        league: League,
        user_id: UUID,
        service: LeagueContextService,
        week: int | None = None,
        writes: Any = None,
    ):
        self.league = league
        self.user_id = user_id
        self.service = service
        self.week = week or league.current_week
        self.writes = writes
        self.auto_approve = False
        self.pending_lineups: list = []
        self._team_ctx: TeamContext | None = None
        self.tools_used: list[str] = []

    async def team_context(self) -> TeamContext:
        if self._team_ctx is None:
            self._team_ctx = await self.service.build_context(self.league, self.week)
        return self._team_ctx

    def invalidate(self) -> None:
        self._team_ctx = None


async def build_tool_context(
    session: AsyncSession,
    user_id: UUID,
    league_id: UUID,
    service: LeagueContextService,
    week: int | None = None,
    writes: Any = None,
) -> ToolContext:
    """The single authorization gate for AI tools."""
    league = await LeagueRepository(session).get_owned(user_id, league_id)
    if league is None:
        raise NotFoundError("League not found.")
    return ToolContext(league, user_id, service, week, writes)


ToolHandler = Callable[[ToolContext, BaseModel], Awaitable[Any]]


class EmptyArgs(BaseModel):
    pass


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: ToolHandler

    def openai_spec(self) -> dict[str, Any]:
        schema = self.args_model.model_json_schema()
        schema.pop("title", None)
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": schema},
        }


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def tool(self, name: str, description: str, args_model: type[BaseModel] = EmptyArgs):
        def deco(fn: ToolHandler) -> ToolHandler:
            self.register(Tool(name=name, description=description, args_model=args_model, handler=fn))
            return fn

        return deco

    def specs(self) -> list[dict[str, Any]]:
        return [t.openai_spec() for t in self.tools.values()]

    def names(self) -> list[str]:
        return list(self.tools.keys())

    async def execute(self, name: str, arguments: dict[str, Any], ctx: ToolContext) -> str:
        """Run a tool and return a JSON string for the model. Never raises."""
        tool = self.tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool '{name}'."})
        try:
            args = tool.args_model.model_validate(arguments or {})
        except ValidationError as exc:
            return json.dumps({"error": "Invalid arguments.", "details": exc.errors(include_url=False)}, default=str)
        try:
            result = await tool.handler(ctx, args)
            ctx.tools_used.append(name)
        except AppError as exc:
            log.info("ai.tool.app_error", tool=name, error=exc.message)
            return json.dumps({"error": exc.message})
        except Exception as exc:  # noqa: BLE001
            log.exception("ai.tool.failed", tool=name)
            return json.dumps({"error": f"Tool failed: {type(exc).__name__}"})
        return json.dumps(_jsonable(result), default=str)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value
