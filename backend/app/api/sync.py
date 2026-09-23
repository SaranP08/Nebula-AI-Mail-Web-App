"""Real-time sync API endpoints:
- POST /api/sync/watch: Set up Gmail push notifications
- POST /webhooks/gmail: Google Pub/Sub push webhook
- GET /api/stream: Server-Sent Events (SSE) live channel
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.broadcaster import broadcaster
from app.services.sync_service import process_history_update, setup_watch

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])


@router.post("/api/sync/watch")
def register_watch(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Register or refresh a Gmail watch on the user's INBOX.

    Pub/Sub topic is configured via GMAIL_PUBSUB_TOPIC in env.
    """
    result = setup_watch(db, current_user)
    return result


@router.post("/webhooks/gmail")
async def gmail_webhook(
    request: Request,
    secret: str = Query(default="", alias="secret"),
) -> dict[str, str]:
    """Pub/Sub push endpoint for Gmail push notifications.

    Verifies secret query parameter against GMAIL_WEBHOOK_SECRET if configured.
    Decodes the base64 message data and processes new emails in the background.
    Always returns 200 quickly per Pub/Sub requirements.
    """
    if settings.gmail_webhook_secret and secret != settings.gmail_webhook_secret:
        logger.warning("Rejected Gmail webhook call: invalid secret '%s'", secret)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret",
        )

    try:
        body = await request.json()
        message = body.get("message", {})
        data_b64 = message.get("data", "")

        if not data_b64:
            logger.warning("Pub/Sub message received without data.")
            return {"status": "ok", "detail": "no_data"}

        # Base64 decode the push notification payload
        decoded_bytes = base64.b64decode(data_b64)
        payload = json.loads(decoded_bytes.decode("utf-8"))

        email_address = payload.get("emailAddress")
        history_id = payload.get("historyId")

        if email_address:
            logger.info("Received push notification for %s with historyId %s", email_address, history_id)
            # Dispatch processing in background so response returns to Pub/Sub immediately
            asyncio.create_task(process_history_update(email_address, str(history_id) if history_id else None))

        return {"status": "ok"}
    except Exception as e:
        logger.error("Error processing Pub/Sub webhook message: %s", e)
        # Always return 200 so Pub/Sub does not keep retrying malformed bodies
        return {"status": "accepted_with_error"}


@router.get("/api/stream")
async def live_stream(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Server-Sent Events (SSE) live channel.

    Streams real-time updates (e.g. `new_mail`) to authenticated clients.
    Sends heartbeat comment (`: ping`) every 20 seconds.
    """
    user_id = current_user.id
    queue = await broadcaster.connect(user_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                # Disconnect if client closed connection
                if await request.is_disconnected():
                    break

                try:
                    # Wait up to 20 seconds for an event from the broadcaster
                    item = await asyncio.wait_for(queue.get(), timeout=20.0)
                    event_name = item.get("event", "message")
                    data = item.get("data", {})
                    yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    # 20-second heartbeat comment
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await broadcaster.disconnect(user_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
