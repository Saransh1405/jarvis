import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from jarvis_ai.config.settings import Settings
from jarvis_ai.llm.factory import LLMProviderError, create_llm_provider
from jarvis_ai.orchestrator.orchestrator import Orchestrator

settings = Settings()
orchestrator = Orchestrator(settings)

app = FastAPI(title="JARVIS AI", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32000)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    provider: str | None = None
    model: str | None = None
    source: str | None = None
    tools_used: list[str] | None = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    llm_status = "ok"
    try:
        create_llm_provider(settings)
    except LLMProviderError as exc:
        llm_status = str(exc)
    return {
        "status": "ready" if llm_status == "ok" else "degraded",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm": llm_status,
    }


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    result = await orchestrator.chat(req.message, req.conversation_id)
    return ChatResponse(**result)


@app.post("/api/v1/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        async for payload in orchestrator.stream_chat(req.message, req.conversation_id):
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
