"""Pydantic schemas for email-related API responses and request bodies."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────
# Shared address representation
# ──────────────────────────────────────────────────────────────

class EmailAddress(BaseModel):
    name: str = ""
    address: str = ""


# ──────────────────────────────────────────────────────────────
# List-view email summary (fast, metadata-only fetch)
# ──────────────────────────────────────────────────────────────

class EmailSummary(BaseModel):
    id: str
    thread_id: str = Field(alias="threadId", default="")
    sender: EmailAddress
    to: list[EmailAddress] = []
    subject: str = ""
    snippet: str = ""
    date: str = ""        # ISO 8601 string
    is_read: bool = True

    model_config = {"populate_by_name": True}


# ──────────────────────────────────────────────────────────────
# Attachment metadata (no binary content in detail view)
# ──────────────────────────────────────────────────────────────

class Attachment(BaseModel):
    attachment_id: str
    filename: str
    mime_type: str
    size: int  # bytes


# ──────────────────────────────────────────────────────────────
# Full email detail
# ──────────────────────────────────────────────────────────────

class EmailDetail(BaseModel):
    id: str
    thread_id: str = Field(alias="threadId", default="")
    sender: EmailAddress
    to: list[EmailAddress] = []
    cc: list[EmailAddress] = []
    reply_to: EmailAddress | None = None
    subject: str = ""
    date: str = ""
    body_html: str = ""
    body_plain: str = ""
    snippet: str = ""
    attachments: list[Attachment] = []
    is_read: bool = True

    model_config = {"populate_by_name": True}


# ──────────────────────────────────────────────────────────────
# Thread (list of messages in a conversation)
# ──────────────────────────────────────────────────────────────

class ThreadMessage(BaseModel):
    """Lightweight message inside a thread response."""
    id: str
    sender: EmailAddress
    date: str
    snippet: str
    body_html: str = ""
    body_plain: str = ""
    is_read: bool = True


class ThreadResponse(BaseModel):
    thread_id: str
    subject: str
    messages: list[ThreadMessage]


# ──────────────────────────────────────────────────────────────
# Send / compose
# ──────────────────────────────────────────────────────────────

class SendEmailRequest(BaseModel):
    to: list[str] = Field(..., min_length=1, description="Recipient addresses")
    cc: list[str] = []
    subject: str = ""
    body: str = Field(..., description="HTML body of the message")
    reply_to_message_id: str | None = Field(
        default=None,
        description="Message-ID header of the message being replied to (sets In-Reply-To)",
    )
    thread_id: str | None = Field(
        default=None,
        description="Gmail threadId to keep the reply in the same thread",
    )


# ──────────────────────────────────────────────────────────────
# List response wrapper
# ──────────────────────────────────────────────────────────────

class EmailListResponse(BaseModel):
    emails: list[EmailSummary]
    next_page_token: str | None = None
    result_size_estimate: int = 0
