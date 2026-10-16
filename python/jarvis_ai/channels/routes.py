"""HTTP routes for Telegram linking and inbound updates."""

import hashlib
import hmac

from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter()


def _token_matches(got: str, want: str) -> bool:
    if not want:
        return False
    digest_got = hashlib.sha256(got.encode("utf-8")).digest()
    digest_want = hashlib.sha256(want.encode("utf-8")).digest()
    return hmac.compare_digest(digest_got, digest_want)


def _service(request: Request):
    service = getattr(request.app.state, "telegram", None)
    if service is None:
        raise HTTPException(status_code=503, detail="telegram is not configured")
    return service


def _user_id(request: Request, x_user_id: str | None) -> str:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database is not configured")
    if not x_user_id:
        raise HTTPException(status_code=401, detail="user_id required")
    return x_user_id


@router.post("/internal/channels/inbound")
async def inbound(
    request: Request,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> dict:
    expected = request.app.state.settings.internal_api_token
    if not expected:
        raise HTTPException(status_code=503, detail="internal api token is not configured")
    if not _token_matches(x_internal_token or "", expected):
        raise HTTPException(status_code=401, detail="invalid internal token")
    update = await request.json()
    if not isinstance(update, dict):
        raise HTTPException(status_code=400, detail="invalid update")
    service = _service(request)
    await service.handle_update(update)
    return {"ok": True}


@router.post("/api/v1/channels/telegram/link")
async def start_link(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> dict:
    user_id = _user_id(request, x_user_id)
    try:
        return await _service(request).start_link(user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/v1/channels/telegram")
async def telegram_status(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> dict:
    user_id = _user_id(request, x_user_id)
    return await _service(request).status(user_id)


@router.delete("/api/v1/channels/telegram")
async def telegram_unlink(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> dict:
    user_id = _user_id(request, x_user_id)
    return await _service(request).unlink(user_id)
