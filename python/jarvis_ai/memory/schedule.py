"""When to enqueue memory extraction."""

from datetime import datetime, timedelta

EXTRACT_EVERY_TURNS = 8
EXTRACT_IDLE = timedelta(minutes=10)


def learns_from_conversations(settings) -> bool:
    value = settings.feature_flags.get("learn_from_conversations", True)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def extract_run_at(user_turns: int, now: datetime) -> datetime:
    if user_turns > 0 and user_turns % EXTRACT_EVERY_TURNS == 0:
        return now
    return now + EXTRACT_IDLE


async def enqueue_memory_extract(
    jobs,
    user_id: str,
    conversation_id: str,
    *,
    user_turns: int,
    last_message_id: str,
    now: datetime,
):
    return await jobs.enqueue(
        kind="memory_extract",
        user_id=user_id,
        run_at=extract_run_at(user_turns, now),
        payload={"conversation_id": conversation_id},
        dedupe_key=f"memory_extract:{conversation_id}:{last_message_id}",
    )
