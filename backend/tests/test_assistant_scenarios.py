"""Backend tests for AI Assistant scenarios A through E with mocked LiteLLM."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.config import settings
from app.models.user import User
from app.services.assistant_service import (
    build_system_prompt,
    stream_assistant_chat,
    validate_llm_config,
)


class MockDelta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class MockChoice:
    def __init__(self, delta):
        self.delta = delta


class MockChunk:
    def __init__(self, content=None, tool_calls=None):
        self.choices = [MockChoice(MockDelta(content, tool_calls))]


class MockToolCall:
    def __init__(self, index, call_id, fn_name, fn_args):
        self.index = index
        self.id = call_id
        self.function = MagicMock()
        self.function.name = fn_name
        self.function.arguments = fn_args


async def async_iter(items):
    for item in items:
        yield item


def parse_sse_events(raw_lines: list[str]) -> list[tuple[str, dict]]:
    """Parse SSE string stream into a list of (event, data_dict) tuples."""
    events = []
    current_event = "message"
    # raw_lines is a list of yielded strings, each containing \n
    all_lines = []
    for chunk in raw_lines:
        all_lines.extend(chunk.split("\n"))

    for line in all_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.replace("event:", "").strip()
        elif line.startswith("data:"):
            raw_data = line.replace("data:", "").strip()
            try:
                data = json.loads(raw_data)
                events.append((current_event, data))
            except Exception:
                pass
    return events


# ── Step 0: LLM Config Validation Tests ────────────────────────────────────────

def test_validate_llm_config_missing_model():
    orig = settings.llm_model
    try:
        settings.llm_model = ""
        err = validate_llm_config()
        assert err is not None
        assert "LLM_MODEL is not configured" in err
    finally:
        settings.llm_model = orig


def test_validate_llm_config_missing_key():
    orig_model = settings.llm_model
    orig_key = settings.gemini_api_key
    try:
        settings.llm_model = "gemini/gemini-1.5-flash"
        settings.gemini_api_key = ""
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            err = validate_llm_config()
            assert err is not None
            assert "GEMINI_API_KEY" in err
            assert "is not configured" in err
    finally:
        settings.llm_model = orig_model
        settings.gemini_api_key = orig_key


def test_validate_llm_config_valid():
    orig_model = settings.llm_model
    orig_key = settings.gemini_api_key
    try:
        settings.llm_model = "gemini/gemini-1.5-flash"
        settings.gemini_api_key = "valid-test-key-123"
        err = validate_llm_config()
        assert err is None
    finally:
        settings.llm_model = orig_model
        settings.gemini_api_key = orig_key


def test_validate_llm_config_groq_missing_key():
    orig_model = settings.llm_model
    orig_key = settings.groq_api_key
    try:
        settings.llm_model = "groq/llama-3.3-70b-versatile"
        settings.groq_api_key = ""
        with patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            err = validate_llm_config()
            assert err is not None
            assert "GROQ_API_KEY" in err
            assert "is not configured" in err
    finally:
        settings.llm_model = orig_model
        settings.groq_api_key = orig_key


def test_validate_llm_config_groq_valid():
    orig_model = settings.llm_model
    orig_key = settings.groq_api_key
    try:
        settings.llm_model = "groq/llama-3.3-70b-versatile"
        settings.groq_api_key = "gsk_valid_key_123"
        err = validate_llm_config()
        assert err is None
    finally:
        settings.llm_model = orig_model
        settings.groq_api_key = orig_key


# ── Scenario A: Compose & Propose Send Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_scenario_a_compose_and_propose_send_no_direct_send():
    """Scenario A: Assistant drafts an email and calls propose_send.

    Assert:
    1. open_compose and fill_compose ui_action events emitted.
    2. confirm_send event emitted with recipient, subject, and body preview.
    3. The assistant NEVER sends the email directly.
    """
    user = User(id="user_1", email="me@example.com", name="Test User", access_token="tok")
    db = MagicMock()

    # Iteration 1: model calls open_compose and fill_compose
    tc1 = MockToolCall(0, "c1", "open_compose", json.dumps({"mode": "new"}))
    tc2 = MockToolCall(1, "c2", "fill_compose", json.dumps({
        "to": "john@example.com",
        "subject": "Meeting Tomorrow",
        "body": "Let's meet at 3pm",
    }))
    chunk1 = MockChunk(tool_calls=[tc1, tc2])

    # Iteration 2: model calls propose_send
    tc3 = MockToolCall(0, "c3", "propose_send", "{}")
    chunk2 = MockChunk(tool_calls=[tc3])

    # Iteration 3: final text
    chunk3 = MockChunk(content="I have prepared your email. Please confirm sending.")

    mock_acompletion = AsyncMock(side_effect=[
        async_iter([chunk1]),
        async_iter([chunk2]),
        async_iter([chunk3]),
    ])

    with patch("litellm.acompletion", mock_acompletion), \
         patch("app.services.assistant_service.validate_llm_config", return_value=None), \
         patch("app.services.gmail_service.send_message") as mock_send:

        stream = stream_assistant_chat(
            user=user,
            db=db,
            messages=[{"role": "user", "content": "Send an email to john@example.com with subject 'Meeting Tomorrow' and body 'Let\'s meet at 3pm'"}],
            ui_state={"view": "list", "folder": "inbox", "currentDraft": {}},
        )

        raw_lines = [line async for line in stream]
        events = parse_sse_events(raw_lines)

        # Assert actions
        ui_actions = [d for ev, d in events if ev == "ui_action"]
        action_names = [a["action"] for a in ui_actions]
        assert "open_compose" in action_names
        assert "fill_compose" in action_names
        assert "propose_send" in action_names

        # Assert confirm_send has the filled details
        confirm_events = [d for ev, d in events if ev == "confirm_send"]
        assert len(confirm_events) == 1
        confirm = confirm_events[0]
        assert confirm["to"] == "john@example.com"
        assert confirm["subject"] == "Meeting Tomorrow"
        assert "Let's meet at 3pm" in confirm["bodyPreview"]

        # Crucial: Assistant NEVER sends email directly
        mock_send.assert_not_called()


# ── Scenario B: Search and Display Tests ───────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario_b_search_and_set_filters():
    """Scenario B: Assistant searches emails and updates the main list via set_filters."""
    user = User(id="user_1", email="me@example.com", name="Test User", access_token="tok")
    db = MagicMock()

    tc1 = MockToolCall(0, "c1", "search_emails", json.dumps({
        "sender": "Sarah",
        "keyword": "project update",
    }))
    tc2 = MockToolCall(1, "c2", "set_filters", json.dumps({
        "sender": "Sarah",
        "keyword": "project update",
    }))
    chunk1 = MockChunk(tool_calls=[tc1, tc2])
    chunk2 = MockChunk(content="Found 1 email from Sarah about project update.")

    mock_acompletion = AsyncMock(side_effect=[
        async_iter([chunk1]),
        async_iter([chunk2]),
    ])

    mock_list_response = MagicMock()
    mock_email = MagicMock()
    mock_email.id = "email_sarah_1"
    mock_email.sender.name = "Sarah Connor"
    mock_email.sender.address = "sarah@example.com"
    mock_email.subject = "project update"
    mock_email.date = "2026-09-18T10:00:00Z"
    mock_email.snippet = "Here is the project update"
    mock_email.is_read = True
    mock_email.model_dump.return_value = {
        "id": "email_sarah_1",
        "subject": "project update",
        "date": "2026-09-18T10:00:00Z",
    }
    mock_list_response.emails = [mock_email]

    with patch("litellm.acompletion", mock_acompletion), \
         patch("app.services.assistant_service.validate_llm_config", return_value=None), \
         patch("app.services.auth_service.refresh_credentials_if_needed"), \
         patch("app.services.gmail_service.list_messages", return_value=mock_list_response):

        stream = stream_assistant_chat(
            user=user,
            db=db,
            messages=[{"role": "user", "content": "Find the email from Sarah about the project update"}],
            ui_state={"view": "list", "folder": "inbox"},
        )

        raw_lines = [line async for line in stream]
        events = parse_sse_events(raw_lines)

        # Emitted email_cards
        card_events = [d for ev, d in events if ev == "email_cards"]
        assert len(card_events) == 1
        assert card_events[0]["cards"][0]["id"] == "email_sarah_1"

        # Emitted set_filters
        ui_actions = [d for ev, d in events if ev == "ui_action"]
        filter_action = next(a for a in ui_actions if a["action"] == "set_filters")
        assert filter_action["params"]["sender"] == "Sarah"
        assert filter_action["params"]["keyword"] == "project update"


# ── Scenario C: Navigate and Open Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario_c_open_email():
    """Scenario C: Assistant opens newest email from person."""
    user = User(id="user_1", email="me@example.com", name="Test User", access_token="tok")
    db = MagicMock()

    tc1 = MockToolCall(0, "c1", "open_email", json.dumps({"email_id": "msg_david_456"}))
    chunk1 = MockChunk(tool_calls=[tc1])
    chunk2 = MockChunk(content="Opened the latest email from David.")

    mock_acompletion = AsyncMock(side_effect=[
        async_iter([chunk1]),
        async_iter([chunk2]),
    ])

    with patch("litellm.acompletion", mock_acompletion), \
         patch("app.services.assistant_service.validate_llm_config", return_value=None):

        stream = stream_assistant_chat(
            user=user,
            db=db,
            messages=[{"role": "user", "content": "Open the latest email from David"}],
            ui_state={"view": "list", "folder": "inbox"},
        )

        raw_lines = [line async for line in stream]
        events = parse_sse_events(raw_lines)

        ui_actions = [d for ev, d in events if ev == "ui_action"]
        open_action = next(a for a in ui_actions if a["action"] == "open_email")
        assert open_action["params"]["email_id"] == "msg_david_456"


# ── Scenario D: Context Awareness (Reply) Tests ───────────────────────────────

@pytest.mark.asyncio
async def test_scenario_d_reply_to_open_email():
    """Scenario D: Assistant opens reply mode with context from openEmail."""
    user = User(id="user_1", email="me@example.com", name="Test User", access_token="tok")
    db = MagicMock()

    open_email_data = {
        "id": "email_msg_789",
        "from": "david@example.com",
        "to": "me@example.com",
        "subject": "Quarterly Planning",
        "date": "2026-09-20T10:00:00Z",
        "body": "Can you review the deck?",
        "threadId": "thread_789",
    }

    tc1 = MockToolCall(0, "c1", "open_compose", json.dumps({
        "mode": "reply",
        "reply_to_message_id": "email_msg_789",
    }))
    tc2 = MockToolCall(1, "c2", "fill_compose", json.dumps({
        "body": "Looks great, approved!",
    }))
    chunk1 = MockChunk(tool_calls=[tc1, tc2])
    chunk2 = MockChunk(content="Drafted your reply to David.")

    mock_acompletion = AsyncMock(side_effect=[
        async_iter([chunk1]),
        async_iter([chunk2]),
    ])

    with patch("litellm.acompletion", mock_acompletion), \
         patch("app.services.assistant_service.validate_llm_config", return_value=None):

        stream = stream_assistant_chat(
            user=user,
            db=db,
            messages=[{"role": "user", "content": "Reply to this saying Looks great, approved!"}],
            ui_state={"view": "detail", "folder": "inbox", "openEmail": open_email_data},
        )

        raw_lines = [line async for line in stream]
        events = parse_sse_events(raw_lines)

        ui_actions = [d for ev, d in events if ev == "ui_action"]
        open_compose = next(a for a in ui_actions if a["action"] == "open_compose")
        assert open_compose["params"]["mode"] == "reply"
        assert open_compose["params"]["reply_to_message_id"] == "email_msg_789"

        fill_compose = next(a for a in ui_actions if a["action"] == "fill_compose")
        assert fill_compose["params"]["body"] == "Looks great, approved!"


# ── Scenario E: Temporal and Filter Awareness Tests ───────────────────────────

def test_scenario_e_system_prompt_temporal_computation():
    """Scenario E: Verify system prompt accurately calculates Monday of this week."""
    ui_state = {
        "currentDatetime": "2026-09-23T14:30:00Z",  # Wednesday
        "timezone": "America/New_York",
        "view": "list",
        "folder": "inbox",
        "activeFilters": {},
    }
    prompt = build_system_prompt(ui_state)

    # 2026-09-23 is Wednesday; Monday of that week is 2026-09-21
    assert "Monday of This Week: 2026-09-21" in prompt
    assert "Current Date (Today): 2026-09-23" in prompt
    assert "Day of Week: Wednesday" in prompt
    assert "User Timezone: America/New_York" in prompt
