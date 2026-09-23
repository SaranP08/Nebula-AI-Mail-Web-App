"""Shared Filters model — the single source of truth for all mail filtering.

This model is used by:
  - GET /api/emails query parameters
  - build_gmail_query() in query_builder.py
  - The AI assistant (future) to construct search queries from natural language

Keep this model pure — no side effects, no I/O.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Filters(BaseModel):
    """All supported mail filter dimensions.

    All fields are optional; omitted fields are simply not applied.
    """

    folder: Literal["inbox", "sent"] = "inbox"
    date_from: date | None = Field(
        default=None,
        description="Include emails ON or AFTER this date (inclusive).",
    )
    date_to: date | None = Field(
        default=None,
        description="Include emails ON or BEFORE this date (inclusive). "
                    "Note: Gmail before: is exclusive, so +1 day is applied internally.",
    )
    sender: str | None = Field(
        default=None,
        description="Filter by sender email or name.",
    )
    keyword: str | None = Field(
        default=None,
        description="Free-text keyword search across subject and body.",
    )
    unread: bool | None = Field(
        default=None,
        description="True = unread only, False = read only, None = all.",
    )
    page_token: str | None = Field(
        default=None,
        description="Gmail pageToken for pagination.",
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum number of messages to return.",
    )
