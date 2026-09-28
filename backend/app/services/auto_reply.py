"""Auto AI fantasy: reply in direct chats the user opted into.

Only a checked manager in this league is answered, and only after they send a
new message. League chat is never posted to. Lineup and roster tools are not used.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.service import AIService
from app.ai.tools import build_tool_context
from app.ai.tools.base import ToolContext
from app.core.errors import AppError, ValidationFailed
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.session import Database
from app.domain.enums import Provider
from app.models import AutoReplySetting, AutoReplyTarget, League, User
from app.repositories import LeagueRepository, TeamRepository
from app.schemas.ai import ChatMessageIn
from app.schemas.league import AutoReplyOut, AutoReplyUpdate, LeagueMessageOut
from app.services.league_context import LeagueContextService
from app.services.sleeper_writes import build_sleeper_write_service

log = get_logger(__name__)

POLL_SECONDS = 20
_lock = asyncio.Lock()
_logged_no_model = False

NOTE_LIMIT = 1000
Compose = Callable[[ToolContext, str, list[ChatMessageIn], str], Awaitable[str | None]]


def fit_reply(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.replace("**", "").replace("__", "").strip().strip("`").strip()
    if not cleaned:
        return None
    if len(cleaned) > 500:
        cleaned = cleaned[:497].rstrip() + "..."
    return cleaned


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def incoming_to_answer(
    messages: list[LeagueMessageOut], enabled_at: datetime, last_message_id: str | None
) -> LeagueMessageOut | None:
    """The latest message from them that we have not already answered."""
    incoming: LeagueMessageOut | None = None
    answered = False
    for message in messages:
        if message.mine:
            if incoming is not None:
                answered = True
        else:
            incoming = message
            answered = False
    if incoming is None or answered or not incoming.text.strip():
        return None
    if incoming.id == last_message_id:
        return None
    if _aware(incoming.created_at) <= _aware(enabled_at):
        return None
    return incoming


def chat_history(messages: list[LeagueMessageOut], incoming: LeagueMessageOut) -> list[ChatMessageIn]:
    picked: list[ChatMessageIn] = []
    for message in messages:
        text = message.text.strip()
        if not text:
            continue
        picked.append(ChatMessageIn(role="assistant" if message.mine else "user", content=text[:2000]))
        if message.id == incoming.id:
            break
    if not picked or picked[-1].role != "user":
        return []
    return picked[-12:]


def _available(league: League) -> bool:
    return league.provider == Provider.SLEEPER and bool(league.fantasy_account.encrypted_credentials)


def clean_note(note: str) -> str:
    cleaned = note.strip()
    if len(cleaned) > NOTE_LIMIT:
        raise ValidationFailed(f"Keep the note under {NOTE_LIMIT} characters.")
    return cleaned


def _out(setting: AutoReplySetting | None, league: League) -> AutoReplyOut:
    targets = setting.targets if setting is not None else []
    return AutoReplyOut(
        enabled=bool(setting and setting.enabled),
        user_ids=[target.sleeper_user_id for target in targets],
        notes={target.sleeper_user_id: (target.note or "").strip() for target in targets},
        available=_available(league),
    )


async def _load(session: AsyncSession, user_id, league_id) -> AutoReplySetting | None:
    result = await session.execute(
        select(AutoReplySetting)
        .where(AutoReplySetting.user_id == user_id, AutoReplySetting.league_id == league_id)
        .options(selectinload(AutoReplySetting.targets))
    )
    return result.scalar_one_or_none()


async def get_auto_reply(session: AsyncSession, user: User, league: League) -> AutoReplyOut:
    return _out(await _load(session, user.id, league.id), league)


async def save_auto_reply(session: AsyncSession, user: User, league: League, body: AutoReplyUpdate) -> AutoReplyOut:
    if league.provider != Provider.SLEEPER:
        raise ValidationFailed("Auto AI fantasy replies in Sleeper leagues.")
    if not league.fantasy_account.encrypted_credentials:
        raise ValidationFailed("Save your Sleeper token in Settings to turn on Auto AI fantasy.")
    me = league.fantasy_account.external_user_id
    owners = {
        team.owner_external_id
        for team in await TeamRepository(session).list_for_league(league.id)
        if team.owner_external_id and team.owner_external_id != me
    }
    wanted = list(dict.fromkeys(user_id.strip() for user_id in body.user_ids if user_id.strip()))
    if any(user_id not in owners for user_id in wanted):
        raise ValidationFailed("Pick managers in this league.")

    setting = await _load(session, user.id, league.id)
    now = utcnow()
    if setting is None:
        setting = AutoReplySetting(user_id=user.id, league_id=league.id, enabled=False, targets=[])
        session.add(setting)
    turning_on = body.enabled and not setting.enabled
    by_id = {target.sleeper_user_id: target for target in list(setting.targets)}
    chosen: list[AutoReplyTarget] = []
    for user_id in wanted:
        target = by_id.get(user_id)
        note = clean_note(body.notes[user_id]) if user_id in body.notes else None
        if target is None:
            target = AutoReplyTarget(sleeper_user_id=user_id, enabled_at=now, note=note or "")
        elif note is not None:
            target.note = note
        chosen.append(target)
    setting.targets = chosen
    setting.enabled = body.enabled
    if turning_on:
        for target in setting.targets:
            target.enabled_at = now
            target.last_message_id = None
    await session.commit()
    return _out(await _load(session, user.id, league.id), league)


async def ensure_auto_reply_tables(db: Database) -> None:
    def _ensure(sync_conn) -> None:
        from sqlalchemy import inspect

        AutoReplySetting.__table__.create(sync_conn, checkfirst=True)
        AutoReplyTarget.__table__.create(sync_conn, checkfirst=True)
        columns = {col["name"] for col in inspect(sync_conn).get_columns("auto_reply_targets")}
        if "note" not in columns:
            sync_conn.exec_driver_sql("ALTER TABLE auto_reply_targets ADD COLUMN note TEXT NOT NULL DEFAULT ''")

    async with db.engine.begin() as conn:
        await conn.run_sync(_ensure)


async def auto_reply_loop(state, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await sweep_auto_replies(state)
        except Exception:
            log.exception("auto_reply.sweep_failed")
        try:
            from app.services.lineup_management import sweep_lineup_management

            await sweep_lineup_management(state)
        except Exception:
            log.exception("lineup_management.sweep_failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=POLL_SECONDS)
        except TimeoutError:
            continue


async def sweep_auto_replies(state, compose: Compose | None = None) -> int:
    """Send at most one new reply per checked manager. Returns how many were sent."""
    global _logged_no_model
    if compose is None and state.llm is None:
        if not _logged_no_model:
            log.info("auto_reply.no_model")
            _logged_no_model = True
        return 0

    async with _lock:
        sent = 0
        async with state.db.session_factory() as session:
            result = await session.execute(
                select(AutoReplySetting)
                .where(AutoReplySetting.enabled.is_(True))
                .options(selectinload(AutoReplySetting.targets))
            )
            for setting in result.scalars().all():
                if not setting.targets:
                    continue
                try:
                    sent += await _sweep_league(state, session, setting, compose)
                except Exception:
                    log.exception("auto_reply.league_failed", league_id=str(setting.league_id))
                    await session.rollback()
        return sent


async def _sweep_league(state, session: AsyncSession, setting: AutoReplySetting, compose: Compose | None) -> int:
    league = await LeagueRepository(session).get_owned(setting.user_id, setting.league_id)
    if league is None or not _available(league):
        return 0
    context = LeagueContextService(
        session, state.nfl_data, state.weekly_stats, state.props, state.sleeper_projections
    )
    writes = build_sleeper_write_service(
        session, context, state.providers, state.cipher, state.settings.sleeper_graphql_url
    )
    chats = {chat.user_id: chat for chat in await writes.direct_chats(league)}
    reply_with = compose or _model_compose(state)
    sent = 0
    for target in list(setting.targets):
        chat = chats.get(target.sleeper_user_id)
        if chat is None or not chat.thread_id:
            continue
        messages = await writes.direct_messages(league, chat.thread_id)
        incoming = incoming_to_answer(messages, target.enabled_at, target.last_message_id)
        if incoming is None:
            continue
        history = chat_history(messages, incoming)
        if not history:
            target.last_message_id = incoming.id
            await session.commit()
            continue
        try:
            ctx = await build_tool_context(
                session, league.fantasy_account.user_id, league.id, context, None, None
            )
            text = fit_reply(await reply_with(ctx, chat.name, history, (target.note or "").strip()))
            if not text:
                target.last_message_id = incoming.id
                await session.commit()
                continue
            await writes.send_direct(league, text, thread_id=chat.thread_id)
            target.last_message_id = incoming.id
            await session.commit()
        except AppError as exc:
            log.warning("auto_reply.compose_failed", league_id=str(league.id), error=exc.message)
            await session.rollback()
            return sent
        sent += 1
        log.info(
            "auto_reply.sent",
            league_id=str(league.id),
            sleeper_user_id=target.sleeper_user_id,
            message_id=incoming.id,
        )
    return sent


def _model_compose(state) -> Compose:
    async def compose(ctx: ToolContext, other_name: str, history: list[ChatMessageIn], note: str) -> str | None:
        return await AIService(state.llm, max_tool_rounds=3).manager_text(ctx, other_name, history, note)

    return compose
