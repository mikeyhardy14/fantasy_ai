"""Review trades that already happened, using the league's transaction record.

A completed trade is not a proposal. The players have already changed teams, so
the review scores the two sides and does not tell anyone to submit it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.ai import TradeAnalysis, TradeReviewResponse, TradeSideSummary
from app.schemas.league import PlayerOut, TransactionOut

_REVIEW = re.compile(
    r"^\s*(?:please\s+)?(?:can you\s+|could you\s+|i want to\s+|i'd like to\s+)?"
    r"(?:review|grade|evaluate|check)\b(?:\s+\w+){0,6}\s+trades?\b"
    r"|^\s*(?:what|which)\s+trades?\s+(?:were|have been|got)\s+made\b",
    re.IGNORECASE,
)


def is_trade_review(text: str) -> bool:
    return _REVIEW.search(text) is not None


@dataclass
class Exchange:
    team_id: str | None
    team_name: str
    sent: list[dict]
    received: list[dict]


def exchanges(adds: list[dict], drops: list[dict]) -> list[Exchange]:
    """Group a trade into what each team sent and received."""
    by_team: dict[str, Exchange] = {}

    def bucket(item: dict) -> Exchange:
        team_id = item.get("team_id")
        team_name = item.get("team_name") or "Unknown team"
        key = str(team_id or team_name)
        row = by_team.get(key)
        if row is None:
            row = Exchange(team_id=str(team_id) if team_id else None, team_name=team_name, sent=[], received=[])
            by_team[key] = row
        return row

    for item in drops:
        bucket(item).sent.append(item)
    for item in adds:
        bucket(item).received.append(item)
    return list(by_team.values())


def user_exchange(rows: list[Exchange], user_team_id: str | None) -> Exchange | None:
    if not user_team_id:
        return None
    return next((row for row in rows if row.team_id == user_team_id), None)


def other_teams(rows: list[Exchange], actor: Exchange) -> str:
    names = [row.team_name for row in rows if row.team_id != actor.team_id or row.team_name != actor.team_name]
    return ", ".join(names) or "the other side"


def score_exchange(
    *,
    actor: str,
    other: str,
    give: list[PlayerOut],
    receive: list[PlayerOut],
    picks: list[str],
    yours: bool,
    already_done: bool,
) -> TradeAnalysis:
    """Score one side of a trade from posted projections."""

    def side(players: list[PlayerOut]) -> TradeSideSummary:
        projected = [player.projected_points for player in players]
        known = all(value is not None for value in projected)
        return TradeSideSummary(
            players=[player.name for player in players],
            positions=[player.position or "?" for player in players],
            projected_points=round(sum(value for value in projected if value is not None), 1) if known and projected else None,
            injured=[player.name for player in players if player.injury_status],
        )

    sent, got = side(give), side(receive)
    gaps: list[str] = []
    if sent.projected_points is None or got.projected_points is None:
        gaps.append("A projection is missing for at least one player, so the point gap is incomplete.")
        verdict = "UNCLEAR"
        effect = "The point gap is incomplete."
    else:
        delta = round(got.projected_points - sent.projected_points, 1)
        if delta > 2:
            verdict = "ACCEPT"
            effect = f"The players received project {delta} points more than the players sent."
        elif delta < -2:
            verdict = "REJECT"
            effect = f"The players sent project {abs(delta)} points more than the players received."
        else:
            verdict = "NEGOTIATE"
            effect = "The two sides are within 2 projected points."
    risks = [f"{player.name} is listed {player.injury_status}." for player in [*give, *receive] if player.injury_status]
    if picks:
        gaps.append("Draft picks in this trade are listed, and they are not scored as players.")
    who = "You" if yours else actor
    summary = f"{who} sent {', '.join(sent.players)} and received {', '.join(got.players)} from {other}. {effect}"
    if picks:
        summary = f"{summary} Picks moved: {', '.join(picks)}."
    if yours and already_done:
        roster = ["This trade is already on your roster."]
        lineup = ["The current lineup already reflects the players you received."]
    elif yours:
        roster = ["This offer is still open."]
        lineup = ["Accepting it would change the players on your roster."]
    else:
        roster = ["Your roster was not part of this trade."]
        lineup = [f"Reviewed from {actor}'s side of a trade with {other}."]
    return TradeAnalysis(
        verdict=verdict,
        summary=summary,
        you_give=sent,
        you_receive=got,
        roster_impact=roster,
        lineup_impact=lineup,
        risks=risks or ["No injury is posted for these players."],
        data_gaps=gaps,
    )


def format_review(review: TradeReviewResponse) -> str:
    who = " ↔ ".join(review.teams) or "Two teams"
    when = f"Week {review.week}" if review.week else "Trade"
    analysis = review.analysis
    if review.involves_user:
        lead = f"**{when} · {who}** ({review.status}). Your roster was in this trade. Verdict: **{analysis.verdict}**."
    else:
        lead = (
            f"**{when} · {who}** ({review.status}). Your roster was not in this trade. "
            f"From {review.perspective}'s side: **{analysis.verdict}**."
        )
    lines = [lead, analysis.summary]
    if analysis.risks:
        lines.append("Risks: " + "; ".join(analysis.risks))
    return "\n\n".join(lines)


def player_ids(items: list[dict]) -> list[str]:
    return [str(item["player_id"]) for item in items if item.get("player_id")]


def pick_lines(picks: list) -> list[str]:
    lines: list[str] = []
    for pick in picks or []:
        if not isinstance(pick, dict):
            continue
        season = pick.get("season")
        rnd = pick.get("round")
        if season and rnd:
            lines.append(f"{season} round {rnd}")
        elif rnd:
            lines.append(f"round {rnd}")
    return lines


def reviewable(trades: list[TransactionOut]) -> list[TransactionOut]:
    """Completed trades first. Open offers are included when nothing has completed."""
    made = [trade for trade in trades if trade.status == "complete"]
    if made:
        return made
    return [trade for trade in trades if trade.status == "pending"]
