"""Rolling conversation summary once a thread gets long."""

from datetime import datetime, timedelta, timezone

SUMMARY_TOKEN_THRESHOLD = 3000
SUMMARY_KEEP = 8
EPISODE_DAYS = 90


def estimate_tokens(messages) -> int:
    return sum(len(getattr(message, "content", "") or "") for message in messages) // 4


async def maybe_roll_summary(conversations, llm, memory, user_id: str, conversation_id: str) -> None:
    if llm is None or getattr(llm, "name", "") == "stub":
        return
    if conversations is None or not hasattr(conversations, "set_summary"):
        return
    messages = await conversations.list_messages(user_id, conversation_id, limit=200)
    if estimate_tokens(messages) < SUMMARY_TOKEN_THRESHOLD or len(messages) <= SUMMARY_KEEP:
        return
    older = messages[:-SUMMARY_KEEP]
    transcript = "\n".join(f"{message.role}: {message.content}" for message in older if message.content)
    if not transcript.strip():
        return
    summary = (
        await llm.complete(
            transcript,
            system="Summarize the earlier part of this conversation in under 120 words. Facts only.",
        )
    ).strip()
    if not summary:
        return
    await conversations.set_summary(user_id, conversation_id, summary)
    if memory is None:
        return
    existing = await memory.list(user_id, kind="episode", limit=1)
    clipped = summary[:500]
    if existing and existing[0].content == clipped:
        return
    await memory.add(
        user_id,
        clipped,
        source="extracted",
        kind="episode",
        importance=2,
        confidence=0.7,
        expires_at=datetime.now(timezone.utc) + timedelta(days=EPISODE_DAYS),
    )
