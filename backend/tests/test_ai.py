"""AI layer: tool authorization, agent loop with a fake LLM, structured validation, demo mode."""

import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.ai.agent import Agent
from app.ai.llm import LLMResponse, ToolCall
from app.ai.service import AIService
from app.ai.tools import build_tool_context, league_tool_registry
from app.api.deps import AppState
from app.core.errors import NotFoundError, ServiceUnavailableError
from app.repositories import LeagueRepository, UserRepository
from app.schemas.ai import TeamAnalysis, TeamAnalysisResponse
from app.services.league_context import LeagueContextService
from tests.conftest import register


class FakeLLM:
    """Scripted LLM: returns queued responses; records what it was asked."""

    model = "fake-model"

    def __init__(self, script: list[LLMResponse]):
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    async def complete(self, messages, *, tools=None, response_model=None, tool_choice=None, temperature=0.3):
        self.calls.append({"messages": messages, "tools": tools, "response_model": response_model})
        if not self.script:
            return LLMResponse(content="done", model=self.model)
        return self.script.pop(0)


VALID_ANALYSIS = {
    "team_summary": "Solid team.",
    "strengths": ["WR depth"],
    "weaknesses": ["RB2 is out"],
    "lineup_changes": [{"slot": "RB", "start_player": "Flash Backup", "sit_player": "Injured Runner", "reason": "Out"}],
    "waiver_priorities": [{"position": "RB", "player_name": "Free Agent", "priority": "HIGH", "reason": "Depth"}],
    "trade_strategy": {"can_trade_away": ["WR"], "should_target": ["RB"], "reasoning": "Surplus WR."},
    "this_week": ["Start Flash Backup"],
    "data_gaps": ["No projections"],
    "confidence": "MEDIUM",
}


async def seed_demo(client, headers) -> str:
    resp = await client.post("/api/demo/league", headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_demo_league_dashboard_and_recommendations(client, auth_headers):
    league_id = await seed_demo(client, auth_headers)
    team = (await client.get(f"/api/leagues/{league_id}/team", headers=auth_headers)).json()
    assert len(team["starters"]) == 9 and len(team["bench"]) >= 4 and team["reserve"]
    assert team["projection_coverage"] in ("full", "partial")
    assert any("BYE" in s["flags"] for s in team["starters"])  # TE on bye storyline
    assert any("QUESTIONABLE" in s["flags"] for s in team["starters"])

    recs = (await client.get(f"/api/leagues/{league_id}/recommendations", headers=auth_headers)).json()
    types = {r["type"] for r in recs}
    assert {"BYE_WEEK", "INJURY_ALERT", "START_SIT"} <= types
    for r in recs:
        assert r["priority"] in ("HIGH", "MEDIUM", "LOW") and r["reason"]

    briefing = (await client.get(f"/api/leagues/{league_id}/briefing", headers=auth_headers)).json()
    assert briefing["week"] == 4 and briefing["attention_items"] and briefing["roster_assessment"]
    assert briefing["generated_by"] == "deterministic"

    standings = (await client.get(f"/api/leagues/{league_id}/standings", headers=auth_headers)).json()
    assert len(standings) == 12
    matchup = (await client.get(f"/api/leagues/{league_id}/matchup", headers=auth_headers)).json()
    assert matchup["opponent"] and matchup["user"]["projected_points"] is not None

    # Idempotent re-seed
    again = await client.post("/api/demo/league", headers=auth_headers)
    assert again.json()["id"] == league_id
    assert len((await client.get("/api/leagues", headers=auth_headers)).json()) == 1


async def test_analyze_without_openai_returns_valid_structured_fallback(client, auth_headers):
    league_id = await seed_demo(client, auth_headers)
    resp = await client.post(f"/api/leagues/{league_id}/ai/analyze", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = TeamAnalysisResponse.model_validate(resp.json())
    assert body.generated_by == "deterministic"
    assert body.analysis.team_summary and body.analysis.this_week
    assert body.analysis.lineup_changes  # bye TE -> backup
    assert body.recommendations


async def test_waiver_suggestions_without_ai_use_roster_rules(client, auth_headers):
    league_id = await seed_demo(client, auth_headers)
    resp = await client.post(f"/api/leagues/{league_id}/ai/waivers", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["generated_by"] == "deterministic"
    assert "Waiver suggestions" in body["message"]
    assert "Weakest positions" in body["message"]


async def test_waiver_suggestions_do_not_offer_lineup_writes(client, auth_headers, session, state: AppState):
    from uuid import UUID

    from app.schemas.ai import WaiverSuggestionsResponse

    league_id = await seed_demo(client, auth_headers)
    owner = await UserRepository(session).get_by_email("mike@example.com")
    ctx = await build_tool_context(session, owner.id, UUID(league_id), LeagueContextService(session, state.nfl_data))
    llm = FakeLLM([LLMResponse(content="Add Spare Tight at TE. No drop. Why: TE depth.")])
    resp = await AIService(llm).suggest_waivers(ctx)
    assert isinstance(resp, WaiverSuggestionsResponse)
    assert resp.generated_by == "openai"
    assert "Spare Tight" in resp.message
    names = [spec["function"]["name"] for spec in llm.calls[0]["tools"]]
    assert "get_available_players" in names
    assert "change_lineup" not in names and "set_lineup" not in names


async def test_chat_fallback_and_validation(client, auth_headers):
    league_id = await seed_demo(client, auth_headers)
    resp = await client.post(
        f"/api/leagues/{league_id}/ai/chat", json={"messages": [{"role": "user", "content": "Who should I start at FLEX?"}]}, headers=auth_headers
    )
    assert resp.status_code == 200 and resp.json()["generated_by"] == "deterministic"
    assert "Lineup" in resp.json()["message"]
    bad = await client.post(f"/api/leagues/{league_id}/ai/chat", json={"messages": []}, headers=auth_headers)
    assert bad.status_code == 422


async def test_trade_analysis_validates_ownership(client, auth_headers):
    league_id = await seed_demo(client, auth_headers)
    team = (await client.get(f"/api/leagues/{league_id}/team", headers=auth_headers)).json()
    mine = team["starters"][1]["player"]["id"]
    available = (await client.get(f"/api/leagues/{league_id}/players?position=RB", headers=auth_headers)).json()
    theirs = available[0]["id"]
    ok = await client.post(f"/api/leagues/{league_id}/ai/trade", json={"give": [mine], "receive": [theirs]}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["analysis"]["verdict"] in ("ACCEPT", "REJECT", "NEGOTIATE", "UNCLEAR")
    bad = await client.post(f"/api/leagues/{league_id}/ai/trade", json={"give": [theirs], "receive": [mine]}, headers=auth_headers)
    assert bad.status_code == 422


async def test_other_team_roster_is_readable(client, auth_headers, session, state: AppState):
    from uuid import UUID

    league_id = await seed_demo(client, auth_headers)
    standings = (await client.get(f"/api/leagues/{league_id}/standings", headers=auth_headers)).json()
    other = next(row for row in standings if not row["is_user_team"])
    resp = await client.get(f"/api/leagues/{league_id}/teams/{other['id']}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["team"]["name"] == other["name"]
    assert body["team"]["is_user_team"] is False
    assert body["starters"]
    missing = await client.get(f"/api/leagues/{league_id}/teams/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert missing.status_code == 404

    owner = await UserRepository(session).get_by_email("mike@example.com")
    ctx = await build_tool_context(session, owner.id, UUID(league_id), LeagueContextService(session, state.nfl_data))
    roster = json.loads(await league_tool_registry.execute("get_team_roster", {"team_id": other["id"]}, ctx))
    assert roster["team"] == other["name"] and roster["is_user"] is False and roster["starters"]


async def test_tool_context_authorization(client, auth_headers, session, state: AppState):
    league_id = await seed_demo(client, auth_headers)
    other_headers = await register(client, "intruder@example.com", "Intruder")
    intruder = await UserRepository(session).get_by_email("intruder@example.com")
    owner = await UserRepository(session).get_by_email("mike@example.com")
    service = LeagueContextService(session, state.nfl_data)
    from uuid import UUID

    with pytest.raises(NotFoundError):
        await build_tool_context(session, intruder.id, UUID(league_id), service)
    ctx = await build_tool_context(session, owner.id, UUID(league_id), service)
    result = json.loads(await league_tool_registry.execute("get_team", {}, ctx))
    assert result["team"]["name"] == "Gridiron Gurus"
    # Player from the pool is reachable; a random uuid is not.
    unknown = json.loads(await league_tool_registry.execute("get_player", {"player_id": "00000000-0000-0000-0000-000000000000"}, ctx))
    assert "error" in unknown
    bad_args = json.loads(await league_tool_registry.execute("compare_players", {"player_ids": ["x"]}, ctx))
    assert "error" in bad_args
    unknown_tool = json.loads(await league_tool_registry.execute("delete_everything", {}, ctx))
    assert "error" in unknown_tool
    resp = await client.post(f"/api/leagues/{league_id}/ai/analyze", headers=other_headers)
    assert resp.status_code == 404


async def test_all_tools_execute_on_demo_league(client, auth_headers, session, state: AppState):
    from uuid import UUID

    league_id = await seed_demo(client, auth_headers)
    owner = await UserRepository(session).get_by_email("mike@example.com")
    ctx = await build_tool_context(session, owner.id, UUID(league_id), LeagueContextService(session, state.nfl_data))
    roster = json.loads(await league_tool_registry.execute("get_roster", {}, ctx))
    pid = roster["starters"][0]["player_id"]
    pid2 = roster["bench"][0]["player_id"]
    for name, args in [
        ("get_team", {}), ("get_league_settings", {}), ("get_current_matchup", {}), ("get_player", {"player_id": pid}),
        ("get_player_stats", {"player_id": pid}), ("get_available_players", {"position": "RB"}),
        ("get_recent_transactions", {}), ("compare_players", {"player_ids": [pid, pid2]}), ("get_roster_needs", {}),
        ("get_standings", {}), ("get_recommendations", {}), ("get_slot_options", {"slot": "FLEX"}),
        ("search_players", {"query": roster["starters"][0]["name"].split()[0]}),
    ]:
        out = json.loads(await league_tool_registry.execute(name, args, ctx))
        assert "error" not in out, (name, out)
    assert set(ctx.tools_used) >= {"get_roster", "get_player_stats", "compare_players"}
    stats = json.loads(await league_tool_registry.execute("get_player_stats", {"player_id": pid}, ctx))
    assert stats["projection"]["points"] is not None and stats["season_stats"]["games_played"] == 3


async def test_agent_loop_executes_tools_then_structured_output(client, auth_headers, session, state: AppState):
    from uuid import UUID

    league_id = await seed_demo(client, auth_headers)
    owner = await UserRepository(session).get_by_email("mike@example.com")
    ctx = await build_tool_context(session, owner.id, UUID(league_id), LeagueContextService(session, state.nfl_data))
    llm = FakeLLM(
        [
            LLMResponse(content=None, tool_calls=[ToolCall(id="c1", name="get_roster", arguments={}), ToolCall(id="c2", name="get_roster_needs", arguments={})],
                        raw_tool_calls=[{"id": "c1", "type": "function", "function": {"name": "get_roster", "arguments": "{}"}},
                                        {"id": "c2", "type": "function", "function": {"name": "get_roster_needs", "arguments": "{}"}}]),
            LLMResponse(content="Analysis prose"),
            LLMResponse(content="not json"),  # first structured attempt invalid -> retry
            LLMResponse(content=json.dumps(VALID_ANALYSIS)),
        ]
    )
    service = AIService(llm)
    result = await service.analyze_team(ctx)
    assert result.generated_by == "openai"
    assert result.analysis.lineup_changes[0].start_player == "Flash Backup"
    assert set(result.tools_used) == {"get_roster", "get_roster_needs"}
    # Tool results were fed back to the model
    tool_msgs = [m for m in llm.calls[1]["messages"] if m["role"] == "tool"]
    assert len(tool_msgs) == 2 and json.loads(tool_msgs[0]["content"])["starters"]
    assert llm.calls[2]["response_model"] is TeamAnalysis


async def test_agent_gives_up_after_invalid_structured_output(client, auth_headers, session, state: AppState):
    from uuid import UUID

    league_id = await seed_demo(client, auth_headers)
    owner = await UserRepository(session).get_by_email("mike@example.com")
    ctx = await build_tool_context(session, owner.id, UUID(league_id), LeagueContextService(session, state.nfl_data))
    llm = FakeLLM([LLMResponse(content="prose"), LLMResponse(content="{}"), LLMResponse(content="{bad")])
    with pytest.raises(ServiceUnavailableError):
        await Agent(llm, league_tool_registry).run([{"role": "user", "content": "go"}], ctx, response_model=TeamAnalysis)


def test_team_analysis_schema_rejects_invalid():
    with pytest.raises(ValidationError):
        TeamAnalysis.model_validate({**VALID_ANALYSIS, "confidence": "VERY HIGH"})
    with pytest.raises(ValidationError):
        TeamAnalysis.model_validate({**VALID_ANALYSIS, "waiver_priorities": [{"position": "RB", "priority": "URGENT", "reason": "x"}]})
    ok = TeamAnalysis.model_validate(VALID_ANALYSIS)
    assert ok.trade_strategy.should_target == ["RB"]


def test_strict_schema_generation():
    from app.ai.llm import _strict_schema

    schema = _strict_schema(TeamAnalysis)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"].keys())
    assert "default" not in schema["properties"]["confidence"]


async def test_chat_with_fake_llm_uses_tools(client, auth_headers, session, state: AppState):
    from uuid import UUID

    league_id = await seed_demo(client, auth_headers)
    owner = await UserRepository(session).get_by_email("mike@example.com")
    ctx = await build_tool_context(session, owner.id, UUID(league_id), LeagueContextService(session, state.nfl_data))
    llm = FakeLLM(
        [
            LLMResponse(content=None, tool_calls=[ToolCall(id="c1", name="get_slot_options", arguments={"slot": "FLEX"})],
                        raw_tool_calls=[{"id": "c1", "type": "function", "function": {"name": "get_slot_options", "arguments": '{"slot":"FLEX"}'}}]),
            LLMResponse(content="Start X at FLEX because..."),
        ]
    )
    from app.schemas.ai import ChatMessageIn

    resp = await AIService(llm).chat(ctx, [ChatMessageIn(role="user", content="Who should I start at FLEX?")])
    assert resp.generated_by == "openai" and resp.tools_used == ["get_slot_options"]
    system = llm.calls[0]["messages"][0]["content"]
    assert "Gridiron Gurus" in system and "Week 4" in system
    assert "change_lineup" in llm.calls[0]["messages"][1]["content"]


def test_gemini_tool_calls_keep_the_thought_signature():
    from app.ai.llm import echo_tool_call

    class Function:
        name = "get_roster"
        arguments = "{}"

    class Call:
        id = "c1"
        type = "function"
        function = Function()

        def model_dump(self):
            return {
                "id": self.id,
                "type": self.type,
                "function": {"name": "get_roster", "arguments": "{}"},
                "extra_content": {"google": {"thought_signature": "sig"}},
            }

    echoed = echo_tool_call(Call())
    assert echoed["extra_content"]["google"]["thought_signature"] == "sig"
    assert echoed["function"]["name"] == "get_roster"


def test_slot_labels_and_free_model_choice():
    from app.ai.llm import build_llm
    from app.ai.tools.league_tools import slot_index
    from app.core.config import Settings

    index, error = slot_index(["QB", "RB", "RB", "WR", "FLEX"], "RB2")
    assert index == 2 and error is None
    index, error = slot_index(["QB", "RB", "RB", "WR", "FLEX"], "RB")
    assert index is None and error and "RB1" in error
    index, error = slot_index(["QB", "SUPER_FLEX"], "superflex")
    assert index == 1 and error is None

    gemini = build_llm(Settings(gemini_api_key="test-gemini", openai_api_key="test-openai", groq_api_key="test-groq"))
    assert gemini is not None and gemini.provider == "gemini" and gemini.model == "gemini-3.5-flash-lite"
    assert "generativelanguage.googleapis.com" in str(gemini._client.base_url)
    groq = build_llm(Settings(gemini_api_key=None, groq_api_key="test-groq", openai_api_key="test-openai"))
    assert groq is not None and groq.provider == "groq"
    paid = build_llm(Settings(gemini_api_key=None, groq_api_key=None, openai_api_key="test-openai"))
    assert paid is not None and paid.provider == "openai"
    assert build_llm(Settings(gemini_api_key=None, groq_api_key=None, openai_api_key=None)) is None


async def test_lineup_tools_name_the_player_and_leave_the_write_to_the_service(client, auth_headers, session, state: AppState):
    from uuid import UUID

    league_id = await seed_demo(client, auth_headers)
    owner = await UserRepository(session).get_by_email("mike@example.com")
    ctx = await build_tool_context(session, owner.id, UUID(league_id), LeagueContextService(session, state.nfl_data))
    roster = json.loads(await league_tool_registry.execute("get_roster", {}, ctx))
    bench = roster["bench"][0]

    blocked = json.loads(
        await league_tool_registry.execute(
            "change_lineup", {"player_name": bench["name"], "destination": "bench"}, ctx
        )
    )
    assert blocked["error"]

    class Recorder:
        def __init__(self):
            self.moves = []
            self.lineups = []

        async def move_player(self, league, body):
            self.moves.append(body)
            return _lineup_reply(roster)

        async def set_lineup(self, league, body):
            self.lineups.append(body)
            return _lineup_reply(roster)

    ctx.writes = Recorder()
    moved = json.loads(
        await league_tool_registry.execute(
            "change_lineup", {"player_name": bench["name"], "destination": "bench"}, ctx
        )
    )
    assert moved["verified"] is True and moved["message"] == "Saved."
    assert ctx.writes.moves[0].player_id == UUID(bench["player_id"])
    assert ctx.writes.moves[0].week == ctx.league.current_week
    assert ctx.writes.moves[0].destination == "bench"

    unknown = json.loads(
        await league_tool_registry.execute("change_lineup", {"player_name": "Nobody Special", "destination": "bench"}, ctx)
    )
    assert "error" in unknown and len(ctx.writes.moves) == 1

    short = json.loads(await league_tool_registry.execute("set_lineup", {"starters": [bench["name"]]}, ctx))
    assert "error" in short and ctx.writes.lineups == []

    names = [row["name"] if row["name"] != "EMPTY" else None for row in roster["starters"]]
    saved = json.loads(await league_tool_registry.execute("set_lineup", {"starters": names}, ctx))
    assert saved["verified"] is True
    assert ctx.writes.lineups[0].starter_player_ids == [
        UUID(row["player_id"]) if row["player_id"] else None for row in roster["starters"]
    ]
    assert ctx.writes.lineups[0].week == ctx.league.current_week

    ctx.writes.moves.clear()
    ctx.pending_lineups.clear()
    held = None
    chosen = None
    starter = None
    slot_name = None
    for index, starter_row in enumerate(roster["starters"]):
        if not starter_row.get("player_id"):
            continue
        label = _numbered_slot(roster["lineup_slots"], index)
        for bench_row in roster["bench"]:
            if not bench_row.get("player_id"):
                continue
            attempt = json.loads(
                await league_tool_registry.execute(
                    "change_lineup",
                    {"player_name": bench_row["name"], "destination": "starter", "slot": label},
                    ctx,
                )
            )
            if attempt.get("pending_approval"):
                held, chosen, starter, slot_name = attempt, bench_row, starter_row, label
                break
            ctx.writes.moves.clear()
            ctx.pending_lineups.clear()
        if held:
            break
    assert held is not None and chosen is not None and starter is not None and slot_name is not None
    assert held["verified"] is False
    assert "was not changed" in held["message"]
    assert "over" in held["summary"]
    assert ctx.writes.moves == []
    assert ctx.pending_lineups[0].player_name == chosen["name"]
    assert ctx.pending_lineups[0].replaces == starter["name"]

    ctx.auto_approve = True
    ctx.pending_lineups.clear()
    applied = json.loads(
        await league_tool_registry.execute(
            "change_lineup",
            {"player_name": chosen["name"], "destination": "starter", "slot": slot_name},
            ctx,
        )
    )
    assert applied["verified"] is True
    assert len(ctx.writes.moves) == 1
    assert ctx.pending_lineups == []


def _numbered_slot(slots: list[str], index: int) -> str:
    name = slots[index]
    same = [i for i, slot in enumerate(slots) if slot == name]
    if len(same) == 1:
        return name
    return f"{name}{same.index(index) + 1}"


def _lineup_reply(roster: dict):
    class Player:
        def __init__(self, name):
            self.name = name

    class Row:
        def __init__(self, slot, name):
            self.slot = slot
            self.player = Player(name) if name else None

    class Team:
        starters = [Row(row["slot"], row["name"] if row["name"] != "EMPTY" else None) for row in roster["starters"]]

    class Reply:
        verified = True
        public_api_confirmed = False
        message = "Saved."
        team = Team()

    return Reply()
