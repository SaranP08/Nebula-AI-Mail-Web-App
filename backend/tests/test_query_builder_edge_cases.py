"""Edge case tests for build_gmail_query."""
from __future__ import annotations

from datetime import date
import pytest
from app.schemas.filters import Filters
from app.services.query_builder import build_gmail_query


def test_sender_with_display_name_and_angle_brackets():
    """Sender filter formatted as 'First Last <user@domain.com>' properly quoted."""
    filters = Filters(folder="inbox", sender="Alice Smith <alice@example.com>")
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert 'from:"Alice Smith <alice@example.com>"' in q


def test_sender_with_plain_name():
    """Sender specified as just a personal name is quoted."""
    filters = Filters(folder="inbox", sender="David Miller")
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert 'from:"David Miller"' in q


def test_sender_plain_email_no_spaces():
    """Sender specified as email without spaces is not quoted."""
    filters = Filters(folder="inbox", sender="david@example.com")
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert "from:david@example.com" in q


def test_keyword_with_quotes():
    """Keyword already having quotes is not double-quoted."""
    filters = Filters(folder="inbox", keyword='"quarterly report"')
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert '"quarterly report"' in q
    assert '""quarterly report""' not in q


def test_keyword_multi_word_unquoted():
    """Keyword without quotes gets quoted for phrase search."""
    filters = Filters(folder="inbox", keyword="quarterly report")
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert '"quarterly report"' in q


def test_date_boundaries_from_only():
    """Date filter with only date_from."""
    filters = Filters(folder="inbox", date_from=date(2026, 9, 1))
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert "after:2026/09/01" in q
    assert "before:" not in q


def test_date_boundaries_to_only():
    """Date filter with only date_to (exclusive end date is incremented by 1 day)."""
    filters = Filters(folder="inbox", date_to=date(2026, 9, 20))
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert "before:2026/09/21" in q
    assert "after:" not in q


def test_date_boundaries_both_same_day():
    """Date filter where date_from and date_to are on the same day covers that full day."""
    filters = Filters(folder="inbox", date_from=date(2026, 9, 15), date_to=date(2026, 9, 15))
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert "after:2026/09/15" in q
    assert "before:2026/09/16" in q


def test_unread_in_sent_folder():
    """Unread filter set in Sent folder."""
    filters = Filters(folder="sent", unread=True)
    q = build_gmail_query(filters)
    assert "in:sent" in q
    assert "is:unread" in q


def test_read_false_in_inbox():
    """Read filter (unread=False) sets is:read."""
    filters = Filters(folder="inbox", unread=False)
    q = build_gmail_query(filters)
    assert "in:inbox" in q
    assert "is:read" in q


def test_all_filters_empty():
    """Default filter object produces only base folder label."""
    filters = Filters(folder="inbox")
    q = build_gmail_query(filters)
    assert q == "in:inbox"
