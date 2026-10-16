"""Account-link rules shared by the in-memory and Postgres channel stores."""

from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from jarvis_ai.channels.base import UserChannel


def apply_link(
    rows: list[UserChannel],
    *,
    user_id: str,
    channel: str,
    external_id: str,
    username: str | None,
    now: datetime,
    new_id: str | None = None,
) -> tuple[list[UserChannel], str]:
    """Return the rows that should replace `rows`, plus 'ok' or 'linked_to_other'."""
    by_external = next(
        (row for row in rows if row.channel == channel and row.external_id == external_id),
        None,
    )
    mine = next((row for row in rows if row.user_id == user_id and row.channel == channel), None)

    if by_external is not None and by_external.user_id == user_id:
        updated = replace(
            by_external,
            status="active",
            external_username=username,
            linked_at=now,
        )
        kept = [row for row in rows if row.id != by_external.id]
        kept.append(updated)
        return kept, "ok"

    if by_external is not None and by_external.status == "active":
        return rows, "linked_to_other"

    remaining = [row for row in rows if by_external is None or row.id != by_external.id]
    if mine is not None:
        remaining = [row for row in remaining if row.id != mine.id]
        remaining.append(
            replace(
                mine,
                external_id=external_id,
                external_username=username,
                status="active",
                linked_at=now,
            )
        )
        return remaining, "ok"

    remaining.append(
        UserChannel(
            id=new_id or str(uuid4()),
            user_id=user_id,
            channel=channel,
            external_id=external_id,
            external_username=username,
            status="active",
            linked_at=now,
        )
    )
    return remaining, "ok"
