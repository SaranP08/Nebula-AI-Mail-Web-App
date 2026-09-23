"""Regression tests for Google OAuth credentials expiry handling.

Ensures that google.auth Credentials.expired can be evaluated without raising:
TypeError: can't compare offset-naive and offset-aware datetimes
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from app.models.user import User
from app.services.auth_service import (
    get_credentials_for_user,
    refresh_credentials_if_needed,
    to_naive_utc,
    upsert_user,
)


def test_to_naive_utc_conversions():
    """Verify to_naive_utc accurately handles None, naive, and offset-aware datetimes."""
    # 1. None
    assert to_naive_utc(None) is None

    # 2. Already naive
    dt_naive = datetime(2026, 9, 20, 15, 30, 0)
    res_naive = to_naive_utc(dt_naive)
    assert res_naive == dt_naive
    assert res_naive.tzinfo is None

    # 3. Aware UTC
    dt_aware_utc = datetime(2026, 9, 20, 15, 30, 0, tzinfo=timezone.utc)
    res_aware_utc = to_naive_utc(dt_aware_utc)
    assert res_aware_utc == datetime(2026, 9, 20, 15, 30, 0)
    assert res_aware_utc.tzinfo is None

    # 4. Aware non-UTC (e.g. +05:30)
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    dt_ist = datetime(2026, 9, 20, 15, 30, 0, tzinfo=tz_ist)
    res_ist = to_naive_utc(dt_ist)
    # 15:30 IST is 10:00 UTC
    assert res_ist == datetime(2026, 9, 20, 10, 0, 0)
    assert res_ist.tzinfo is None

    # 5. Aware negative offset (e.g. -04:00)
    tz_edt = timezone(timedelta(hours=-4))
    dt_edt = datetime(2026, 9, 20, 12, 0, 0, tzinfo=tz_edt)
    res_edt = to_naive_utc(dt_edt)
    # 12:00 EDT is 16:00 UTC
    assert res_edt == datetime(2026, 9, 20, 16, 0, 0)
    assert res_edt.tzinfo is None


def test_credentials_expired_with_aware_expiry():
    """Regression test: User with timezone-aware token_expiry must not raise on creds.expired."""
    # Future expiry (unexpired)
    future_aware = datetime.now(timezone.utc) + timedelta(hours=2)
    user_future = User(
        id="user_aware_future",
        email="future@example.com",
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        token_expiry=future_aware,
    )
    creds_future = get_credentials_for_user(user_future)
    assert creds_future.expiry is not None
    assert creds_future.expiry.tzinfo is None
    # Must evaluate cleanly without raising TypeError
    assert creds_future.expired is False

    # Past expiry (expired)
    past_aware = datetime.now(timezone.utc) - timedelta(hours=2)
    user_past = User(
        id="user_aware_past",
        email="past@example.com",
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        token_expiry=past_aware,
    )
    creds_past = get_credentials_for_user(user_past)
    assert creds_past.expiry is not None
    assert creds_past.expiry.tzinfo is None
    assert creds_past.expired is True


def test_credentials_expired_with_naive_expiry():
    """Regression test: User with offset-naive token_expiry must not raise on creds.expired."""
    # Future naive expiry
    future_naive = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)
    user_future = User(
        id="user_naive_future",
        email="naive_future@example.com",
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        token_expiry=future_naive,
    )
    creds_future = get_credentials_for_user(user_future)
    assert creds_future.expiry is not None
    assert creds_future.expiry.tzinfo is None
    assert creds_future.expired is False

    # Past naive expiry
    past_naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    user_past = User(
        id="user_naive_past",
        email="naive_past@example.com",
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        token_expiry=past_naive,
    )
    creds_past = get_credentials_for_user(user_past)
    assert creds_past.expiry is not None
    assert creds_past.expiry.tzinfo is None
    assert creds_past.expired is True


def test_credentials_expired_with_none_expiry():
    """User with None token_expiry should produce Credentials where expired is False."""
    user = User(
        id="user_none_expiry",
        email="none@example.com",
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        token_expiry=None,
    )
    creds = get_credentials_for_user(user)
    assert creds.expiry is None
    assert creds.expired is False


def test_refresh_credentials_if_needed_persists_naive_utc():
    """When tokens are refreshed, the updated expiry must be persisted as naive UTC."""
    mock_db = MagicMock()
    user = User(
        id="user_to_refresh",
        email="refresh@example.com",
        access_token="expired_token",
        refresh_token="valid_refresh_token",
        # Set an expired aware datetime
        token_expiry=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    new_aware_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    with patch("google.auth.transport.requests.Request"):
        with patch("app.services.auth_service.Credentials") as mock_creds_cls:
            mock_creds_inst = MagicMock()
            mock_creds_inst.expired = True
            mock_creds_inst.refresh_token = "valid_refresh_token"
            mock_creds_inst.token = "new_access_token"
            mock_creds_inst.expiry = new_aware_expiry
            mock_creds_cls.return_value = mock_creds_inst

            creds = refresh_credentials_if_needed(user, mock_db)
            assert creds is mock_creds_inst
            assert user.access_token == "new_access_token"
            # user.token_expiry must be normalized to naive UTC
            assert user.token_expiry.tzinfo is None
            assert user.token_expiry == to_naive_utc(new_aware_expiry)
            mock_db.commit.assert_called_once()
