"""HTTP API for viewing, editing, and deleting memories."""

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter()


class MemoryItem(BaseModel):
    id: str
    kind: str
    content: str
    source: str
    importance: int
    confidence: float
    created_at: str
    updated_at: str | None = None


class MemoryPatch(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _item(fact) -> MemoryItem:
    return MemoryItem(
        id=fact.id,
        kind=fact.kind,
        content=fact.content,
        source=fact.source,
        importance=fact.importance,
        confidence=fact.confidence,
        created_at=_iso(fact.created_at) or "",
        updated_at=_iso(fact.updated_at),
    )


def _store(request: Request):
    memory = getattr(request.app.state, "memory", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="memory store is not configured")
    return memory


def _user_id(request: Request, x_user_id: str | None) -> str:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return x_user_id or ""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    return x_user_id


@router.get("/api/v1/memories", response_model=list[MemoryItem])
async def list_memories(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[MemoryItem]:
    user_id = _user_id(request, x_user_id)
    if not user_id:
        return []
    rows = await _store(request).list(user_id, kind=kind, query=q, limit=limit, offset=offset)
    return [_item(row) for row in rows]


@router.get("/api/v1/memories/export")
async def export_memories(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> dict:
    user_id = _user_id(request, x_user_id)
    if not user_id:
        return {"memories": []}
    rows = await _store(request).list(user_id, limit=500, offset=0)
    return {"memories": [_item(row).model_dump() for row in rows]}


@router.patch("/api/v1/memories/{memory_id}", response_model=MemoryItem)
async def update_memory(
    memory_id: str,
    body: MemoryPatch,
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> MemoryItem:
    user_id = _user_id(request, x_user_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    store = _store(request)
    status = await store.update_content(user_id, memory_id, body.content.strip())
    if status == "missing":
        raise HTTPException(status_code=404, detail="memory not found")
    if status == "pending_embed":
        jobs = getattr(request.app.state, "jobs", None)
        if jobs is not None:
            from datetime import datetime, timezone

            await jobs.enqueue(
                kind="memory_embed",
                user_id=user_id,
                run_at=datetime.now(timezone.utc),
                payload={"memory_id": memory_id},
                dedupe_key=f"memory_embed:{memory_id}",
            )
    row = await store.get(user_id, memory_id)
    if row is None:
        raise HTTPException(status_code=404, detail="memory not found")
    return _item(row)


@router.delete("/api/v1/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> dict:
    user_id = _user_id(request, x_user_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    deleted = await _store(request).delete(user_id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="memory not found")
    return {"deleted": memory_id}


@router.delete("/api/v1/memories")
async def forget_everything(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> dict:
    user_id = _user_id(request, x_user_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    count = await _store(request).forget_all(user_id)
    return {"deleted": count}
