"""Email API routes.

All endpoints require authentication via the signed session cookie.

GET  /api/emails                   → List emails with filters + pagination
GET  /api/emails/{id}              → Full email detail
POST /api/emails/send              → Send / reply to email
POST /api/emails/{id}/read         → Mark as read
POST /api/emails/{id}/unread       → Mark as unread
GET  /api/threads/{thread_id}      → Get full conversation thread
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.email import EmailDetail, EmailListResponse, SendEmailRequest, ThreadResponse
from app.schemas.filters import Filters
from app.services import auth_service, gmail_service

router = APIRouter(prefix="/api", tags=["emails"])


def _get_authenticated_credentials(user: User, db: Session):
    """Helper: return refreshed credentials for an authenticated user."""
    return auth_service.refresh_credentials_if_needed(user, db)


# ── List emails ───────────────────────────────────────────────────────────────

@router.get("/emails", response_model=EmailListResponse)
def list_emails(
    request: Request,
    folder: str = "inbox",
    page_token: Optional[str] = None,
    limit: int = 25,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sender: Optional[str] = None,
    keyword: Optional[str] = None,
    unread: Optional[bool] = None,
    db: Session = Depends(get_db),
) -> EmailListResponse:
    """List emails in the given folder with optional filters and pagination."""
    user = auth_service.get_current_user(request=request, db=db)
    creds = _get_authenticated_credentials(user, db)

    filters = Filters(
        folder=folder,  # type: ignore[arg-type]
        page_token=page_token,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        sender=sender,
        keyword=keyword,
        unread=unread,
    )

    return gmail_service.list_messages(creds, filters)


# ── Email detail ──────────────────────────────────────────────────────────────

@router.get("/emails/{message_id}", response_model=EmailDetail)
def get_email(
    message_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> EmailDetail:
    """Get full email detail including parsed HTML/plain body and attachments."""
    user = auth_service.get_current_user(request=request, db=db)
    creds = _get_authenticated_credentials(user, db)
    return gmail_service.get_message(creds, message_id)


# ── Send email ────────────────────────────────────────────────────────────────

@router.post("/emails/send", status_code=status.HTTP_201_CREATED)
def send_email(
    payload: SendEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Send a new email or reply to an existing thread."""
    user = auth_service.get_current_user(request=request, db=db)
    creds = _get_authenticated_credentials(user, db)
    sent = gmail_service.send_message(creds, payload, sender_email=user.email)
    return {"id": sent.get("id"), "threadId": sent.get("threadId"), "status": "sent"}


# ── Mark read / unread ────────────────────────────────────────────────────────

@router.post("/emails/{message_id}/read")
def mark_read(
    message_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Mark a message as read (remove UNREAD label)."""
    user = auth_service.get_current_user(request=request, db=db)
    creds = _get_authenticated_credentials(user, db)
    gmail_service.modify_labels(creds, message_id, add_labels=[], remove_labels=["UNREAD"])
    return {"id": message_id, "isRead": True}


@router.post("/emails/{message_id}/unread")
def mark_unread(
    message_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Mark a message as unread (add UNREAD label)."""
    user = auth_service.get_current_user(request=request, db=db)
    creds = _get_authenticated_credentials(user, db)
    gmail_service.modify_labels(creds, message_id, add_labels=["UNREAD"], remove_labels=[])
    return {"id": message_id, "isRead": False}


# ── Thread view ───────────────────────────────────────────────────────────────

@router.get("/threads/{thread_id}", response_model=ThreadResponse)
def get_thread(
    thread_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ThreadResponse:
    """Get all messages in a conversation thread."""
    user = auth_service.get_current_user(request=request, db=db)
    creds = _get_authenticated_credentials(user, db)
    return gmail_service.get_thread(creds, thread_id)
