"""Pure Gmail query builder.

build_gmail_query(filters: Filters) -> str

Converts a Filters model into a Gmail search query string.
This function is intentionally pure (no I/O, no side effects) so it is:
  - Easy to unit-test
  - Reusable by the AI assistant (future step)
  - Reusable by any route handler

Gmail search operator reference:
  https://support.google.com/mail/answer/7190
"""
from __future__ import annotations

from datetime import timedelta

from app.schemas.filters import Filters


def build_gmail_query(filters: Filters) -> str:
    """Build a Gmail search query string from a Filters model.

    Rules applied:
      - folder:  in:inbox  /  in:sent
      - date_from:  after:YYYY/MM/DD  (inclusive — Gmail after: is inclusive)
      - date_to:  before:YYYY/MM/DD  (Gmail before: is exclusive, so +1 day)
      - sender:  from:<sender>
      - unread:  True → is:unread  |  False → is:read  |  None → omitted
      - keyword:  appended verbatim (Gmail full-text search)

    Returns an empty string if no filters are active (fetches all mail).
    """
    parts: list[str] = []

    # Folder
    if filters.folder == "inbox":
        parts.append("in:inbox")
    elif filters.folder == "sent":
        parts.append("in:sent")

    # Date range
    if filters.date_from:
        # after: is inclusive in Gmail — no adjustment needed
        parts.append(f"after:{filters.date_from.strftime('%Y/%m/%d')}")

    if filters.date_to:
        # before: is EXCLUSIVE in Gmail, so add one day to make it inclusive
        exclusive_end = filters.date_to + timedelta(days=1)
        parts.append(f"before:{exclusive_end.strftime('%Y/%m/%d')}")

    # Sender
    if filters.sender and filters.sender.strip():
        sender = filters.sender.strip()
        # Quote if contains spaces (e.g., display names)
        if " " in sender:
            parts.append(f'from:"{sender}"')
        else:
            parts.append(f"from:{sender}")

    # Read/unread state
    if filters.unread is True:
        parts.append("is:unread")
    elif filters.unread is False:
        parts.append("is:read")

    # Free-text keyword (appended last so it can include Gmail operators too)
    if filters.keyword and filters.keyword.strip():
        keyword = filters.keyword.strip()
        # Quote multi-word phrases for exact match
        if " " in keyword and not keyword.startswith('"'):
            parts.append(f'"{keyword}"')
        else:
            parts.append(keyword)

    return " ".join(parts)
