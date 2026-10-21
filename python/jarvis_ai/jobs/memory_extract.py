"""Background jobs that embed and extract personal memories."""

import logging
from datetime import datetime, timezone

from jarvis_ai.channels.base import OutboundMessage
from jarvis_ai.jobs.models import ScheduledJob
from jarvis_ai.memory.candidates import candidates_from_turns
from jarvis_ai.memory.consolidate import consolidate, llm_judge
from jarvis_ai.memory.schedule import learns_from_conversations

logger = logging.getLogger(__name__)


class MemoryEmbedHandler:
    def __init__(self, memory, embedder) -> None:
        self._memory = memory
        self._embedder = embedder

    async def __call__(self, job: ScheduledJob) -> None:
        if self._embedder is None:
            raise RuntimeError("embedding provider is not configured")
        memory_id = str(job.payload.get("memory_id") or "")
        if not memory_id:
            return
        row = await self._memory.get(job.user_id, memory_id)
        if row is None or row.embedding is not None:
            return
        vector = await self._embedder.embed(row.content)
        await self._memory.set_embedding(job.user_id, memory_id, vector, self._embedder.model)


class MemoryExtractHandler:
    def __init__(self, memory, conversations, settings_store, llm, notifier) -> None:
        self._memory = memory
        self._conversations = conversations
        self._settings = settings_store
        self._llm = llm
        self._notifier = notifier

    async def __call__(self, job: ScheduledJob) -> None:
        settings = await self._settings.get(job.user_id)
        if not learns_from_conversations(settings):
            logger.info("memory_extract skipped learn_from_conversations user_id=%s", job.user_id)
            return
        conversation_id = str(job.payload.get("conversation_id") or "")
        if not conversation_id or self._conversations is None:
            return
        messages = await self._conversations.list_messages(job.user_id, conversation_id, limit=40)
        turns = [message.content for message in messages if message.role == "user" and message.content]
        candidates = await candidates_from_turns(self._llm, turns[-12:])

        async def judge(new: str, old: str) -> str:
            return await llm_judge(self._llm, new, old)

        stored: list[str] = []
        for candidate in candidates:
            result = await consolidate(
                self._memory,
                job.user_id,
                candidate,
                judge,
                sensitive_ok=True,
            )
            if result.action in {"new", "superseded"}:
                stored.append(result.content)
        if not stored or self._notifier is None:
            return
        preview = stored[0]
        if len(stored) == 1:
            text = f"I noted that {preview} /memory to review."
        else:
            text = f"I noted {len(stored)} things, including {preview} /memory to review."
        await self._notifier.notify(
            job.user_id,
            "memory",
            OutboundMessage(text=text, format="plain"),
            dedupe_key=f"memory_note:{job.dedupe_key or job.id}",
        )


async def enqueue_unembedded(memory, jobs, now: datetime | None = None) -> int:
    moment = now or datetime.now(timezone.utc)
    rows = await memory.list_unembedded(50)
    for memory_id, user_id in rows:
        await jobs.enqueue(
            kind="memory_embed",
            user_id=user_id,
            run_at=moment,
            payload={"memory_id": memory_id},
            dedupe_key=f"memory_embed:{memory_id}",
        )
    return len(rows)
