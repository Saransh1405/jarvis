import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from jarvis_ai.actions.memory import InMemoryPendingActionsStore
from jarvis_ai.actions.repository import PendingActionsRepository
from jarvis_ai.channels.routes import router as channel_router
from jarvis_ai.channels.service import TelegramService
from jarvis_ai.config.settings import Settings
from jarvis_ai.delivery import build_delivery_stack
from jarvis_ai.conversations import ConversationsRepository, InMemoryConversationsStore
from jarvis_ai.db import create_pool, run_migrations
from jarvis_ai.memory.store import InMemoryMemoryStore, PostgresMemoryStore
from jarvis_ai.notes.memory import InMemoryNotesStore
from jarvis_ai.notes.repository import NotesRepository
from jarvis_ai.observability.tool_log import NoOpToolCallLogger, ToolCallLogger
from jarvis_ai.jobs.memory import InMemoryJobQueue
from jarvis_ai.orchestrator.orchestrator import Orchestrator
from jarvis_ai.reminders.memory import InMemoryRemindersStore
from jarvis_ai.reminders.repository import RemindersRepository
from jarvis_ai.user_settings import InMemoryUserSettingsStore, UserSettingsRepository

settings = Settings()


def _configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s %(message)s",
        force=True,
    )
    logging.getLogger("jarvis_ai").setLevel(level)


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool: asyncpg.Pool | None = None
    stack = None

    if settings.database_url:
        pool = await create_pool(settings.database_url)
        await run_migrations(pool)
        notes = NotesRepository(pool)
        pending = PendingActionsRepository(pool)
        reminders = RemindersRepository(pool)
        memory = PostgresMemoryStore(pool)
        tool_logger = ToolCallLogger(pool)
        conversations = ConversationsRepository(pool)
        user_settings = UserSettingsRepository(pool)
        stack = build_delivery_stack(pool, settings, user_settings, reminders, pending)
        jobs = stack.jobs
    else:
        notes = InMemoryNotesStore()
        pending = InMemoryPendingActionsStore()
        reminders = InMemoryRemindersStore()
        memory = InMemoryMemoryStore()
        tool_logger = NoOpToolCallLogger()
        conversations = None
        user_settings = InMemoryUserSettingsStore()
        jobs = InMemoryJobQueue()

    app.state.db_pool = pool
    app.state.settings = settings
    app.state.notifications = stack.notifications if stack is not None else None
    app.state.orchestrator = Orchestrator(
        settings,
        notes=notes,
        reminders=reminders,
        memory=memory,
        pending_actions=pending,
        tool_logger=tool_logger,
        conversations=conversations,
        user_settings=user_settings,
        jobs=jobs,
    )
    telegram_client = stack.telegram_client if stack is not None else None
    app.state.telegram = None
    app.state.notifier = stack.notifier if stack is not None else None
    if stack is not None:
        from jarvis_ai.channels.repository import ChannelsRepository

        app.state.telegram = TelegramService(
            channels=ChannelsRepository(pool),
            conversations=conversations,
            orchestrator=app.state.orchestrator,
            telegram=stack.adapters.get("telegram"),
            settings_store=user_settings,
            notes=notes,
            reminders=reminders,
            bot_username=settings.telegram_bot_username,
            feature_enabled=settings.feature_telegram,
            jobs=jobs,
            briefs=stack.briefs,
        )
    yield
    if telegram_client is not None:
        await telegram_client.aclose()
    if pool is not None:
        await pool.close()


app = FastAPI(title="JARVIS AI", version="0.1.0", lifespan=lifespan)
app.include_router(channel_router)


def get_orchestrator() -> Orchestrator:
    return app.state.orchestrator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32000)
    conversation_id: str | None = None


class PendingActionResponse(BaseModel):
    action_id: str | None = None
    tool_call_id: str
    tool_name: str
    arguments: dict


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    provider: str | None = None
    model: str | None = None
    source: str | None = None
    tools_used: list[str] | None = None
    pending_action: PendingActionResponse | None = None


class NotificationItem(BaseModel):
    id: str
    kind: str
    channel: str
    status: str
    ref_id: str | None = None
    error: str | None = None
    body: str | None = None
    created_at: str
    sent_at: str | None = None


class ActionStatusResponse(BaseModel):
    action_id: str
    status: str
    message: str | None = None
    tools_used: list[str] | None = None
    conversation_id: str | None = None


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@app.get("/api/v1/notifications", response_model=list[NotificationItem])
async def list_notifications(
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[NotificationItem]:
    user_id = require_user_id(x_user_id)
    notifications = getattr(app.state, "notifications", None)
    if notifications is None or not user_id:
        return []
    rows = await notifications.list_for_user(user_id, limit)
    return [
        NotificationItem(
            id=row["id"],
            kind=row["kind"],
            channel=row["channel"],
            status=row["status"],
            ref_id=row.get("ref_id"),
            error=row.get("error"),
            body=row.get("body"),
            created_at=_iso(row.get("created_at")) or "",
            sent_at=_iso(row.get("sent_at")),
        )
        for row in rows
    ]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    from jarvis_ai.llm.factory import LLMProviderError, create_llm_provider

    llm_status = "ok"
    try:
        create_llm_provider(settings)
    except LLMProviderError as exc:
        llm_status = str(exc)

    db_status = "not_configured"
    pool = getattr(app.state, "db_pool", None)
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_status = "ok"
        except Exception as exc:
            db_status = f"error: {exc}"

    degraded = llm_status != "ok" or (settings.database_url and db_status != "ok")
    return {
        "status": "degraded" if degraded else "ready",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm": llm_status,
        "database": db_status,
    }


def require_user_id(x_user_id: str | None) -> str:
    pool = getattr(app.state, "db_pool", None)
    if pool is None:
        return x_user_id or ""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    return x_user_id


class ConversationSummary(BaseModel):
    id: str
    title: str | None = None
    created_at: str
    updated_at: str


class MessageItem(BaseModel):
    id: str
    role: str
    content: str
    metadata: dict
    created_at: str


@app.get("/api/v1/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> list[ConversationSummary]:
    user_id = require_user_id(x_user_id)
    orchestrator = get_orchestrator()
    items = await orchestrator.list_conversations_for_user(user_id)
    return [ConversationSummary(**item) for item in items]


@app.get("/api/v1/conversations/{conversation_id}/messages", response_model=list[MessageItem])
async def list_conversation_messages(
    conversation_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> list[MessageItem]:
    user_id = require_user_id(x_user_id)
    orchestrator = get_orchestrator()
    rows = await orchestrator.list_messages_for_user(user_id, conversation_id)
    if rows is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return [MessageItem(**row) for row in rows]


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> ChatResponse:
    user_id = require_user_id(x_user_id) if getattr(app.state, "db_pool", None) else x_user_id
    orchestrator = get_orchestrator()
    result = await orchestrator.chat(req.message, req.conversation_id, user_id=user_id or None)
    status_code = result.pop("status_code", None)
    if status_code:
        raise HTTPException(status_code=status_code, detail=result.get("error", "error"))
    return ChatResponse(**result)


@app.post("/api/v1/chat/stream")
async def chat_stream(
    req: ChatRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> StreamingResponse:
    user_id = require_user_id(x_user_id) if getattr(app.state, "db_pool", None) else x_user_id
    orchestrator = get_orchestrator()

    async def event_generator() -> AsyncIterator[str]:
        async for payload in orchestrator.stream_chat(
            req.message, req.conversation_id, user_id=user_id or None
        ):
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/v1/actions/{action_id}/approve", response_model=ChatResponse)
async def approve_action(
    action_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> ChatResponse:
    user_id = require_user_id(x_user_id) if getattr(app.state, "db_pool", None) else x_user_id
    orchestrator = get_orchestrator()
    result = await orchestrator.approve_action(action_id, user_id or None)
    status_code = result.pop("status_code", None)
    if status_code:
        raise HTTPException(status_code=status_code, detail=result.get("error", "error"))
    return ChatResponse(
        message=result["message"],
        conversation_id=result["conversation_id"],
        provider=result.get("provider"),
        model=result.get("model"),
        source=result.get("source"),
        tools_used=result.get("tools_used"),
        pending_action=None,
    )


@app.post("/api/v1/actions/{action_id}/reject", response_model=ActionStatusResponse)
async def reject_action(
    action_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> ActionStatusResponse:
    user_id = require_user_id(x_user_id) if getattr(app.state, "db_pool", None) else x_user_id
    orchestrator = get_orchestrator()
    result = await orchestrator.reject_action(action_id, user_id or None)
    status_code = result.pop("status_code", None)
    if status_code:
        raise HTTPException(status_code=status_code, detail=result.get("error", "error"))
    return ActionStatusResponse(
        action_id=result["action_id"],
        status=result["status"],
        message=result.get("message"),
    )
