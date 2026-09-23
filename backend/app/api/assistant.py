"""Assistant chat API endpoint:
- POST /api/assistant/chat: Streams SSE events controlling UI and responses
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.assistant_service import stream_assistant_chat
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class AssistantChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    ui_state: dict[str, Any] = Field(default_factory=dict)


@router.post("/chat")
async def assistant_chat(
    payload: AssistantChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """POST /api/assistant/chat streams Server-Sent Events.

    Executes LiteLLM agent loop with server and UI tools, emitting:
    - text_delta
    - tool_call
    - ui_action
    - email_cards
    - confirm_send
    - error
    - done
    """
    messages_dicts = [m.model_dump() for m in payload.messages]

    generator = stream_assistant_chat(
        user=current_user,
        db=db,
        messages=messages_dicts,
        ui_state=payload.ui_state,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
