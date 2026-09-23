"""Unit tests for build_gmail_query.

These tests are pure — no I/O, no database, no network calls.
Run with: pytest tests/ -v
"""
from __future__ import annotations

from datetime import date

import pytest

from app.schemas.filters import Filters
from app.services.query_builder import build_gmail_query


# ── Folder ────────────────────────────────────────────────────────────────────

def test_default_folder_is_inbox():
    q = build_gmail_query(Filters())
    assert "in:inbox" in q


def test_sent_folder():
    q = build_gmail_query(Filters(folder="sent"))
    assert "in:sent" in q
    assert "in:inbox" not in q


# ── Date range ────────────────────────────────────────────────────────────────

def test_date_from_only():
    q = build_gmail_query(Filters(date_from=date(2024, 1, 15)))
    assert "after:2024/01/15" in q
    assert "before:" not in q


def test_date_to_adds_one_day_for_exclusive_before():
    """Gmail before: is exclusive, so we add one day to make date_to inclusive."""
    q = build_gmail_query(Filters(date_to=date(2024, 1, 15)))
    # date_to=2024-01-15, before: should be 2024/01/16
    assert "before:2024/01/16" in q


def test_date_range_full():
    q = build_gmail_query(Filters(date_from=date(2024, 3, 1), date_to=date(2024, 3, 31)))
    assert "after:2024/03/01" in q
    assert "before:2024/04/01" in q  # +1 day for exclusive end


def test_date_to_month_boundary():
    """Ensure end-of-month correctly rolls over to next month."""
    q = build_gmail_query(Filters(date_to=date(2024, 1, 31)))
    assert "before:2024/02/01" in q


def test_date_to_year_boundary():
    """Ensure end-of-year correctly rolls into next year."""
    q = build_gmail_query(Filters(date_to=date(2023, 12, 31)))
    assert "before:2024/01/01" in q


# ── Sender ────────────────────────────────────────────────────────────────────

def test_sender_simple_email():
    q = build_gmail_query(Filters(sender="alice@example.com"))
    assert "from:alice@example.com" in q


def test_sender_with_spaces_is_quoted():
    q = build_gmail_query(Filters(sender="Alice Smith"))
    assert 'from:"Alice Smith"' in q


def test_sender_empty_string_is_ignored():
    q = build_gmail_query(Filters(sender=""))
    assert "from:" not in q


def test_sender_whitespace_only_is_ignored():
    q = build_gmail_query(Filters(sender="   "))
    assert "from:" not in q


# ── Unread ────────────────────────────────────────────────────────────────────

def test_unread_true():
    q = build_gmail_query(Filters(unread=True))
    assert "is:unread" in q
    assert "is:read" not in q


def test_unread_false():
    q = build_gmail_query(Filters(unread=False))
    assert "is:read" in q
    assert "is:unread" not in q


def test_unread_none_omits_filter():
    q = build_gmail_query(Filters(unread=None))
    assert "is:unread" not in q
    assert "is:read" not in q


# ── Keyword ───────────────────────────────────────────────────────────────────

def test_keyword_single_word():
    q = build_gmail_query(Filters(keyword="invoice"))
    assert "invoice" in q


def test_keyword_multi_word_is_quoted():
    q = build_gmail_query(Filters(keyword="quarterly report"))
    assert '"quarterly report"' in q


def test_keyword_already_quoted_not_double_quoted():
    q = build_gmail_query(Filters(keyword='"exact phrase"'))
    # Should not add another layer of quotes
    assert '"exact phrase"' in q
    assert '""exact phrase""' not in q


def test_keyword_empty_is_ignored():
    q = build_gmail_query(Filters(keyword=""))
    # Should only have the folder part
    assert q == "in:inbox"


# ── Combined filters ──────────────────────────────────────────────────────────

def test_all_filters_combined():
    q = build_gmail_query(
        Filters(
            folder="inbox",
            date_from=date(2024, 6, 1),
            date_to=date(2024, 6, 30),
            sender="boss@company.com",
            keyword="budget",
            unread=True,
        )
    )
    assert "in:inbox" in q
    assert "after:2024/06/01" in q
    assert "before:2024/07/01" in q
    assert "from:boss@company.com" in q
    assert "is:unread" in q
    assert "budget" in q


def test_no_filters_returns_folder_only():
    q = build_gmail_query(Filters())
    assert q == "in:inbox"


def test_sent_folder_no_other_filters():
    q = build_gmail_query(Filters(folder="sent"))
    assert q == "in:sent"


# ── Order of parts ────────────────────────────────────────────────────────────

def test_query_is_space_separated():
    q = build_gmail_query(Filters(folder="inbox", keyword="hello", unread=True))
    parts = q.split()
    assert "in:inbox" in parts
    assert "is:unread" in parts
    assert "hello" in parts


def test_no_double_spaces():
    q = build_gmail_query(Filters(folder="inbox", sender="alice@example.com"))
    assert "  " not in q
