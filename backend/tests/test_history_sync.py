"""Unit tests for Gmail history sync and webhook processing."""
from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from httplib2 import Response

from app.database import Base, SessionLocal, engine
from app.models.user import User
from app.schemas.email import EmailAddress, EmailSummary
from app.services import gmail_service
from app.services.broadcaster import broadcaster
from app.services.sync_service import process_history_update, setup_watch


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(User).delete()
    user = User(
        id="user_123",
        email="testuser@example.com",
        name="Test User",
        access_token="fake_token",
        refresh_token="fake_refresh",
        last_history_id="1000",
    )
    db.add(user)
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(User).delete()
    db.commit()
    db.close()


def test_list_history_with_added_messages():
    """Mock Gmail history.list returning messageAdded records."""
    mock_service = MagicMock()
    mock_creds = MagicMock()

    # Mock history().list().execute()
    mock_history_resp = {
        "historyId": "1050",
        "history": [
            {
                "messagesAdded": [
                    {"message": {"id": "msg_001", "threadId": "th_001"}}
                ]
            }
        ],
    }
    mock_service.users().history().list().execute.return_value = mock_history_resp

    # Mock batch request for metadata
    batch_mock = MagicMock()
    def mock_batch_add(req, callback=None, request_id=None):
        raw_msg = {
            "id": request_id,
            "threadId": "th_001",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Hello there!",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "To", "value": "testuser@example.com"},
                    {"name": "Subject", "value": "Welcome to Nebula"},
                    {"name": "Date", "value": "Sun, 20 Sep 2026 10:00:00 +0000"},
                ]
            },
        }
        if callback:
            callback(request_id, raw_msg, None)

    batch_mock.add.side_effect = mock_batch_add
    mock_service.new_batch_http_request.return_value = batch_mock

    with patch("app.services.gmail_service._gmail_service", return_value=mock_service):
        emails, new_history_id = gmail_service.list_history(mock_creds, "1000")

    assert new_history_id == "1050"
    assert len(emails) == 1
    assert emails[0].id == "msg_001"
    assert emails[0].subject == "Welcome to Nebula"
    assert emails[0].sender.address == "alice@example.com"
    assert emails[0].is_read is False


def test_list_history_404_recovery():
    """When historyId is outdated/purged (404), fallback to getProfile historyId."""
    mock_service = MagicMock()
    mock_creds = MagicMock()

    http_404 = HttpError(resp=Response({"status": 404}), content=b"History ID not found")
    mock_service.users().history().list().execute.side_effect = http_404
    mock_service.users().getProfile().execute.return_value = {
        "emailAddress": "testuser@example.com",
        "historyId": "2000",
    }

    with patch("app.services.gmail_service._gmail_service", return_value=mock_service):
        emails, fallback_history_id = gmail_service.list_history(mock_creds, "9999999")

    assert emails == []
    assert fallback_history_id == "2000"


@pytest.mark.asyncio
async def test_process_history_update_publishes_event():
    """process_history_update should fetch new emails and broadcast new_mail."""
    fake_email = EmailSummary(
        id="msg_live_1",
        threadId="th_live_1",
        sender=EmailAddress(name="Bob", address="bob@example.com"),
        to=[EmailAddress(name="Test", address="testuser@example.com")],
        subject="Urgent review",
        snippet="Please check this out",
        date="2026-09-20T10:00:00Z",
        is_read=False,
    )

    with patch("app.services.sync_service.refresh_credentials_if_needed", return_value=MagicMock()), \
         patch("app.services.gmail_service.list_history", return_value=([fake_email], "1080")), \
         patch.object(broadcaster, "publish", return_value=1) as mock_publish:

        count = await process_history_update("testuser@example.com", "1080")

        assert count == 1
        mock_publish.assert_called_once()
        args = mock_publish.call_args[0]
        assert args[0] == "user_123"
        assert args[1] == "new_mail"
        assert args[2]["email"]["id"] == "msg_live_1"

    # Verify db updated with new historyId
    db = SessionLocal()
    user = db.query(User).filter(User.id == "user_123").first()
    assert user.last_history_id == "1080"
    db.close()


def test_pubsub_webhook_secret_and_payload_decode():
    """Test webhook endpoint decodes base64 and verifies secret."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.config import settings

    client = TestClient(app)

    # Set secret for test
    original_secret = settings.gmail_webhook_secret
    settings.gmail_webhook_secret = "super-secret-key"

    try:
        # Invalid secret should return 403
        resp = client.post("/webhooks/gmail?secret=wrong", json={})
        assert resp.status_code == 403

        # Valid payload base64 encoded
        data_json = json.dumps({"emailAddress": "testuser@example.com", "historyId": "1090"})
        data_b64 = base64.b64encode(data_json.encode("utf-8")).decode("utf-8")

        with patch("app.api.sync.process_history_update") as mock_update:
            resp = client.post(
                "/webhooks/gmail?secret=super-secret-key",
                json={"message": {"data": data_b64, "messageId": "12345"}},
            )
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
    finally:
        settings.gmail_webhook_secret = original_secret
