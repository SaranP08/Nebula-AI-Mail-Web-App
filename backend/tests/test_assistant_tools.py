"""Unit tests for AI Assistant tool schemas and validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.assistant_tools import (
    SERVER_TOOLS,
    TOOLS_SCHEMA,
    UI_TOOLS,
    SearchEmailsArgs,
    GetEmailArgs,
    SetFiltersArgs,
    ShowResultsArgs,
    OpenEmailArgs,
    NavigateArgs,
    OpenComposeArgs,
    FillComposeArgs,
    validate_tool_args,
)


def test_tools_schema_structure():
    """Verify that all tools in TOOLS_SCHEMA follow OpenAI/LiteLLM specification."""
    assert len(TOOLS_SCHEMA) >= 8
    all_names = set()
    for tool in TOOLS_SCHEMA:
        assert tool.get("type") == "function"
        fn = tool.get("function", {})
        name = fn.get("name")
        assert name
        all_names.add(name)
        assert fn.get("description")
        assert "parameters" in fn
        assert fn["parameters"].get("type") == "object"

    # All server and UI tools must be represented
    for t in SERVER_TOOLS:
        assert t in all_names
    for t in UI_TOOLS:
        assert t in all_names


def test_search_emails_validation():
    """Test search_emails arguments parsing and constraints."""
    args = validate_tool_args("search_emails", {
        "folder": "inbox",
        "date_from": "2026-09-01",
        "date_to": "2026-09-20",
        "sender": "Alice",
        "keyword": "urgent",
        "unread": True,
        "limit": 15,
    })
    assert isinstance(args, SearchEmailsArgs)
    assert args.folder == "inbox"
    assert args.limit == 15
    assert args.unread is True

    # Limit constraints (max 25, min 1)
    with pytest.raises(ValidationError):
        validate_tool_args("search_emails", {"limit": 50})
    with pytest.raises(ValidationError):
        validate_tool_args("search_emails", {"limit": 0})


def test_get_email_validation():
    """Test get_email required parameters."""
    args = validate_tool_args("get_email", {"id": "msg_xyz_123"})
    assert isinstance(args, GetEmailArgs)
    assert args.id == "msg_xyz_123"

    with pytest.raises(ValidationError):
        validate_tool_args("get_email", {})


def test_show_results_validation():
    """Test show_results requires non-empty array of email_ids."""
    args = validate_tool_args("show_results", {"email_ids": ["id1", "id2"]})
    assert isinstance(args, ShowResultsArgs)
    assert args.email_ids == ["id1", "id2"]

    with pytest.raises(ValidationError):
        validate_tool_args("show_results", {})


def test_navigate_validation():
    """Test navigate views."""
    args = validate_tool_args("navigate", {"view": "compose"})
    assert isinstance(args, NavigateArgs)
    assert args.view == "compose"

    # Invalid view should raise ValidationError
    with pytest.raises(ValidationError):
        validate_tool_args("navigate", {"view": "unknown_tab"})


def test_fill_compose_validation():
    """Test fill_compose optional fields."""
    args = validate_tool_args("fill_compose", {
        "to": "bob@example.com",
        "subject": "Hi Bob",
        "body": "Let's meet at 2pm.",
    })
    assert isinstance(args, FillComposeArgs)
    assert args.to == "bob@example.com"
    assert args.subject == "Hi Bob"
    assert args.body == "Let's meet at 2pm."


def test_unknown_tool_raises():
    """Passing an unknown tool name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown tool"):
        validate_tool_args("hack_system", {})
