"""Tool schemas and Pydantic validation for the AI Assistant.

Separates tools into:
1. SERVER tools: executed directly by the backend (Gmail API queries / details)
2. UI tools: emitted as ui_action events to the frontend to drive the Zustand store
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


# ── Pydantic argument schemas ──────────────────────────────────────────────────

class SearchEmailsArgs(BaseModel):
    folder: Literal["inbox", "sent"] = "inbox"
    date_from: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    date_to: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    sender: str | None = Field(default=None, description="Sender name or email address")
    keyword: str | None = Field(default=None, description="Keyword search query")
    unread: bool | None = Field(default=None, description="True for unread only, False for read only")
    limit: int = Field(default=10, ge=1, le=25, description="Max number of emails to return (1-25)")


class GetEmailArgs(BaseModel):
    id: str = Field(..., description="Gmail message ID")


class SetFiltersArgs(BaseModel):
    folder: Literal["inbox", "sent"] | None = None
    date_from: str | None = None
    date_to: str | None = None
    sender: str | None = None
    keyword: str | None = None
    unread: bool | None = None


class ClearFiltersArgs(BaseModel):
    pass


class ShowResultsArgs(BaseModel):
    email_ids: list[str] = Field(..., description="List of email IDs to display in the main list")


class OpenEmailArgs(BaseModel):
    email_id: str = Field(..., description="The message ID to open in the reading pane")


class NavigateArgs(BaseModel):
    view: Literal["list", "compose", "detail"]
    folder: Literal["inbox", "sent"] | None = None


class OpenComposeArgs(BaseModel):
    mode: Literal["new", "reply", "replyAll", "forward"] = "new"
    reply_to_message_id: str | None = None


class FillComposeArgs(BaseModel):
    to: str | None = None
    cc: str | None = None
    subject: str | None = None
    body: str | None = None


class ProposeSendArgs(BaseModel):
    to: str | None = None
    subject: str | None = None
    body: str | None = None


# ── Tool sets ──────────────────────────────────────────────────────────────────

SERVER_TOOLS = {"search_emails", "get_email"}
UI_TOOLS = {
    "set_filters",
    "clear_filters",
    "show_results",
    "open_email",
    "navigate",
    "open_compose",
    "fill_compose",
    "propose_send",
}

TOOL_MODEL_MAP: dict[str, type[BaseModel]] = {
    "search_emails": SearchEmailsArgs,
    "get_email": GetEmailArgs,
    "set_filters": SetFiltersArgs,
    "clear_filters": ClearFiltersArgs,
    "show_results": ShowResultsArgs,
    "open_email": OpenEmailArgs,
    "navigate": NavigateArgs,
    "open_compose": OpenComposeArgs,
    "fill_compose": FillComposeArgs,
    "propose_send": ProposeSendArgs,
}


def validate_tool_args(tool_name: str, arguments: dict[str, Any]) -> BaseModel:
    """Validate tool arguments using strict Pydantic model."""
    model_cls = TOOL_MODEL_MAP.get(tool_name)
    if not model_cls:
        raise ValueError(f"Unknown tool '{tool_name}'")
    return model_cls.model_validate(arguments)


# ── LiteLLM / OpenAI function definitions ──────────────────────────────────────

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": (
                "Search Gmail messages on the server using filters. Returns a compact list of matching emails "
                "(id, from, subject, date, snippet, isRead). Always use this when the user asks to find, list, "
                "or check emails."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "enum": ["inbox", "sent"],
                        "description": "Folder to search in (default: inbox)",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Start date in ISO format YYYY-MM-DD",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End date in ISO format YYYY-MM-DD",
                    },
                    "sender": {
                        "type": "string",
                        "description": "Sender name or email address",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Text keyword or topic to search for",
                    },
                    "unread": {
                        "type": "boolean",
                        "description": "True for unread only, False for read only",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of emails to retrieve (default: 10, max: 25)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_email",
            "description": (
                "Fetch the full email content (sender, recipients, subject, date, body, snippet) for a specific email ID. "
                "Use this whenever you need to read or summarize an email."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "The unique Gmail message ID",
                    },
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_filters",
            "description": (
                "Updates the filter state of the user's main mail list in the UI and automatically refetches emails "
                "so the main list visibly updates. Use this when the user asks to filter the list."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "enum": ["inbox", "sent"]},
                    "date_from": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "sender": {"type": "string"},
                    "keyword": {"type": "string"},
                    "unread": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_filters",
            "description": "Clears all active filters in the user's UI to show all emails in the current folder.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_results",
            "description": (
                "Directs the user's main UI to display exactly the specified list of email IDs. "
                "Call this immediately after search_emails so the main list reflects the found emails."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "email_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of email IDs found from search",
                    },
                },
                "required": ["email_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_email",
            "description": "Opens the email reading pane in the UI for the specified email ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The ID of the email to open",
                    },
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Navigates the main application view (inbox, sent, compose).",
            "parameters": {
                "type": "object",
                "properties": {
                    "view": {
                        "type": "string",
                        "enum": ["list", "compose", "detail"],
                        "description": "The destination view",
                    },
                    "folder": {
                        "type": "string",
                        "enum": ["inbox", "sent"],
                        "description": "Folder if navigating to list",
                    },
                },
                "required": ["view"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_compose",
            "description": (
                "Opens the compose form in the UI. For replies or forwards, specify the mode and "
                "optionally reply_to_message_id (or it defaults to the currently open email)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["new", "reply", "replyAll", "forward"],
                        "description": "Draft mode",
                    },
                    "reply_to_message_id": {
                        "type": "string",
                        "description": "ID of email to reply to or forward",
                    },
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill_compose",
            "description": (
                "Fills in visible compose form fields. The UI animates typing into the To, Subject, and Body fields. "
                "Use this to write or modify email drafts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address(es)"},
                    "cc": {"type": "string", "description": "CC recipient email address(es)"},
                    "subject": {"type": "string", "description": "Subject line"},
                    "body": {"type": "string", "description": "Body message text"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_send",
            "description": (
                "Prompts the human user to confirm sending the drafted email by rendering a confirmation card. "
                "The assistant NEVER sends directly without explicit user confirmation."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
