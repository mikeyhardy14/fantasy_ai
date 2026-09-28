"""Auto AI fantasy replies only to checked managers, and only to a new message."""

from datetime import UTC, datetime, timedelta

from app.schemas.league import LeagueMessageOut
from app.services.auto_reply import fit_reply, incoming_to_answer, sweep_auto_replies
from tests.fixtures import sleeper as fx
from tests.test_sleeper_lineup import TOKEN, _import, _save_token, install_graphql


def _message(message_id: str, author_id: str, text: str, created: datetime, mine: bool) -> LeagueMessageOut:
    return LeagueMessageOut(id=message_id, author_name="Rival", text=text, created_at=created, mine=mine)


def test_incoming_message_is_the_one_we_have_not_answered():
    now = datetime.now(UTC)
    old = _message("1", fx.OPP_USER_ID, "old", now - timedelta(days=1), False)
    fresh = _message("2", fx.OPP_USER_ID, "You there?", now + timedelta(minutes=1), False)
    assert incoming_to_answer([old], now, None) is None
    assert incoming_to_answer([fresh], now, None) is fresh
    assert incoming_to_answer([fresh], now, "2") is None
    mine = _message("3", fx.USER_ID, "Yeah", now + timedelta(minutes=2), True)
    assert incoming_to_answer([fresh, mine], now, None) is None
    assert fit_reply("  **I'll check.**  ") == "I'll check."
    assert fit_reply("") is None
    long = "word " * 200
    assert fit_reply(long) is not None and len(fit_reply(long) or "") <= 500


def _future_ms() -> int:
    return int((datetime.now(UTC) + timedelta(minutes=2)).timestamp() * 1000)


async def test_auto_reply_answers_a_new_message_once(client, auth_headers, sleeper_mock, state):
    seen = install_graphql(
        sleeper_mock,
        {
            "dms": [
                {
                    "dm_id": "dm-rival",
                    "dm_type": "single",
                    "last_message_time": _future_ms(),
                    "recent_users": [
                        {"user_id": fx.USER_ID, "display_name": "MikeFantasy"},
                        {"user_id": fx.OPP_USER_ID, "display_name": "Rival"},
                    ],
                }
            ],
            "messages": [
                {
                    "message_id": "m-new",
                    "created": _future_ms(),
                    "author_id": fx.OPP_USER_ID,
                    "author_display_name": "Rival",
                    "text": "Who should I start?",
                }
            ],
        },
    )
    league = await _import(client, auth_headers)
    blocked = await client.put(
        f"/api/leagues/{league['id']}/auto-reply",
        json={"enabled": True, "user_ids": [fx.OPP_USER_ID]},
        headers=auth_headers,
    )
    assert blocked.status_code == 422

    await _save_token(client, auth_headers, TOKEN)
    saved = await client.put(
        f"/api/leagues/{league['id']}/auto-reply",
        json={
            "enabled": True,
            "user_ids": [fx.OPP_USER_ID],
            "notes": {fx.OPP_USER_ID: "Keep it short. No trade talk."},
        },
        headers=auth_headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["enabled"] is True
    assert saved.json()["user_ids"] == [fx.OPP_USER_ID]
    assert saved.json()["notes"][fx.OPP_USER_ID] == "Keep it short. No trade talk."
    assert saved.json()["available"] is True

    calls: list[tuple[str, str, str]] = []

    async def compose(_ctx, other_name, history, note):
        calls.append((other_name, history[-1].content, note))
        return "I'll check the matchup."

    assert await sweep_auto_replies(state) == 0
    assert "sent" not in seen
    assert await sweep_auto_replies(state, compose=compose) == 1
    assert calls == [("Rival", "Who should I start?", "Keep it short. No trade talk.")]
    assert seen["sent"]["parent_id"] == "dm-rival"
    assert seen["sent"]["parent_type"] == "dm"
    assert seen["sent"]["text"] == "I'll check the matchup."
    assert await sweep_auto_replies(state, compose=compose) == 0
    assert calls == [("Rival", "Who should I start?", "Keep it short. No trade talk.")]


async def test_auto_reply_skips_old_answered_and_unchecked_people(client, auth_headers, sleeper_mock, state):
    mode = {
        "dms": [
            {
                "dm_id": "dm-rival",
                "dm_type": "single",
                "last_message_time": 1_700_000_000_000,
                "recent_users": [
                    {"user_id": fx.USER_ID, "display_name": "MikeFantasy"},
                    {"user_id": fx.OPP_USER_ID, "display_name": "Rival"},
                ],
            }
        ],
        "messages": [
            {
                "message_id": "old",
                "created": 1_600_000_000_000,
                "author_id": fx.OPP_USER_ID,
                "author_display_name": "Rival",
                "text": "From last year",
            }
        ],
    }
    seen = install_graphql(sleeper_mock, mode)
    league = await _import(client, auth_headers)
    await _save_token(client, auth_headers, TOKEN)
    league_id = league["id"]

    async def compose(_ctx, _name, _history, _note):
        return "Should not send."

    saved = await client.put(
        f"/api/leagues/{league_id}/auto-reply",
        json={"enabled": True, "user_ids": [fx.OPP_USER_ID]},
        headers=auth_headers,
    )
    assert saved.status_code == 200, saved.text
    assert await sweep_auto_replies(state, compose=compose) == 0
    assert "sent" not in seen

    stranger = await client.put(
        f"/api/leagues/{league_id}/auto-reply",
        json={"enabled": True, "user_ids": ["999"]},
        headers=auth_headers,
    )
    assert stranger.status_code == 422

    off = await client.put(
        f"/api/leagues/{league_id}/auto-reply",
        json={"enabled": False, "user_ids": [fx.OPP_USER_ID]},
        headers=auth_headers,
    )
    assert off.status_code == 200
    mode["messages"] = [
        {
            "message_id": "fresh",
            "created": _future_ms(),
            "author_id": fx.OPP_USER_ID,
            "author_display_name": "Rival",
            "text": "New offer",
        }
    ]
    assert await sweep_auto_replies(state, compose=compose) == 0
    assert "sent" not in seen

    mode["messages"] = [
        {
            "message_id": "fresh",
            "created": _future_ms(),
            "author_id": fx.OPP_USER_ID,
            "author_display_name": "Rival",
            "text": "New offer",
        },
        {
            "message_id": "mine",
            "created": _future_ms() + 1000,
            "author_id": fx.USER_ID,
            "author_display_name": "Mike",
            "text": "Already answered",
        },
    ]
    on = await client.put(
        f"/api/leagues/{league_id}/auto-reply",
        json={"enabled": True, "user_ids": [fx.OPP_USER_ID]},
        headers=auth_headers,
    )
    assert on.status_code == 200
    assert await sweep_auto_replies(state, compose=compose) == 0
    assert "sent" not in seen
