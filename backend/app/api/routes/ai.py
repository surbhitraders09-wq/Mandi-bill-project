"""
Optional NVIDIA "AI brain" HTTP surface.

Everything here is additive and non-destructive: if the brain is disabled
(no key in .env) the endpoints still answer 200 with clear status; they never
raise so the /mobile flow and automation stay untouched.

Endpoints
---------
GET  /api/ai/status   -> health of the brain (never exposes the key)
POST /api/ai/chat     -> {messages:[{role,content}...]} -> {reply:"..."}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import ai_brain

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    messages: List[Dict[str, str]] = Field(..., min_length=1)
    max_tokens: Optional[int] = Field(default=600, ge=1, le=4096)


class ChatResponse(BaseModel):
    enabled: bool
    reply: str


@router.get("/status")
async def brain_status() -> Dict[str, Any]:
    return ai_brain.health_info()


@router.post("/chat", response_model=ChatResponse)
async def brain_chat(req: ChatRequest) -> ChatResponse:
    reply = await ai_brain.chat(req.messages, max_tokens=req.max_tokens or 600)
    return ChatResponse(enabled=ai_brain.health_info()["brain"]["enabled"], reply=reply)
