"""AI Assistant Service powered by LiteLLM.

Implements an agent loop (up to 6 tool iterations) that streams SSE events:
- text_delta: chunks of the assistant's reply text
- tool_call: tool invocation notifications (name, args)
- ui_action: structured UI commands dispatched to the client's Zustand store
- email_cards: compact preview cards for emails found via search
- confirm_send: confirmation card payload for human-in-the-loop email sending
- error: error message if tool or model execution fails
- done: signal that the response stream is complete
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.schemas.filters import Filters
from app.services import gmail_service
from app.services.assistant_tools import (
    SERVER_TOOLS,
    TOOLS_SCHEMA,
    UI_TOOLS,
    validate_tool_args,
)
from app.services.auth_service import refresh_credentials_if_needed
from app.services.query_builder import build_gmail_query

logger = logging.getLogger(__name__)


def validate_llm_config() -> str | None:
    """Validate that LLM model and required provider API keys are properly configured.

    Returns an error message string if invalid or missing, or None if valid.
    """
    if not settings.llm_model or not settings.llm_model.strip():
        return "LLM_MODEL is not configured in backend environment."

    model = settings.llm_model.strip().lower()

    # IMPORTANT: Check Groq BEFORE OpenAI.
    # Groq model names such as groq/openai/gpt-oss-20b
    # contain both "groq" and "openai".
    if "groq" in model:
        key = getattr(settings, "groq_api_key", None) or os.environ.get("GROQ_API_KEY", "")
        if not key or key.strip() in {
            "your_groq_api_key_here",
            "change_me",
            "",
        }:
            return "GROQ_API_KEY is not configured or contains a placeholder value."

    elif "gemini" in model or "vertex" in model:
        key = (
            settings.gemini_api_key
            or os.environ.get("GEMINI_API_KEY", "")
            or os.environ.get("VERTEXAI_API_KEY", "")
        )
        if not key or key.strip() in {
            "your_gemini_api_key_here",
            "change_me",
            "",
        }:
            return "GEMINI_API_KEY (or VERTEXAI_API_KEY) is not configured or contains a placeholder value."

    elif "gpt" in model or "openai" in model:
        key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key or key.strip() in {
            "your_openai_api_key_here",
            "change_me",
            "",
        }:
            return "OPENAI_API_KEY is not configured or contains a placeholder value."

    elif "claude" in model or "anthropic" in model:
        key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key or key.strip() in {
            "your_anthropic_api_key_here",
            "change_me",
            "",
        }:
            return "ANTHROPIC_API_KEY is not configured or contains a placeholder value."

    else:
        has_any_key = any([
            settings.gemini_api_key,
            settings.openai_api_key,
            settings.anthropic_api_key,
            getattr(settings, "groq_api_key", None),
            os.environ.get("GEMINI_API_KEY"),
            os.environ.get("OPENAI_API_KEY"),
            os.environ.get("ANTHROPIC_API_KEY"),
            os.environ.get("GROQ_API_KEY"),
        ])

        if not has_any_key:
            return f"No API key configured for LLM model '{settings.llm_model}'."

    return None


def build_system_prompt(ui_state: dict[str, Any]) -> str:
    """Construct dynamic system prompt with temporal and UI context."""
    current_dt_str = ui_state.get("currentDatetime") or datetime.now(timezone.utc).isoformat()
    try:
        dt = datetime.fromisoformat(current_dt_str.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(timezone.utc)

    weekday = dt.strftime("%A")
    today_iso = dt.strftime("%Y-%m-%d")
    # Monday of the current week (weekday() is 0 for Monday)
    monday_dt = dt - timedelta(days=dt.weekday())
    monday_iso = monday_dt.strftime("%Y-%m-%d")
    ten_days_ago_iso = (dt - timedelta(days=10)).strftime("%Y-%m-%d")
    seven_days_ago_iso = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
    yesterday_iso = (dt - timedelta(days=1)).strftime("%Y-%m-%d")

    timezone_str = ui_state.get("timezone") or "UTC"
    view = ui_state.get("view", "list")
    folder = ui_state.get("folder", "inbox")
    filters = ui_state.get("activeFilters", {})
    open_email = ui_state.get("openEmail")
    current_draft = ui_state.get("currentDraft")

    filters_repr = json.dumps(filters) if filters else "None"
    open_email_repr = json.dumps(open_email) if open_email else "None"
    draft_repr = json.dumps(current_draft) if current_draft else "None"

    return f"""You are Outlook Copilot, an AI assistant that directly CONTROLS THE USER INTERFACE of the mail application.
The human user sees whatever UI actions you perform in real-time. A text-only reply without invoking appropriate UI tools is a FAILURE.

PRIMARY DIRECTIVES:
- You drive the mail UI. Prefer acting through tools over merely describing what to do.
- Never claim an email was sent unless the user confirmed and the API succeeded.
- The assistant NEVER sends emails by itself; calling propose_send presents a confirmation card to the human user.
- Never invent recipients, email addresses, or email content. If details or intent are missing or ambiguous, ask a short, crisp clarifying question.

TEMPORAL CONTEXT (User's Current Date & Time):
- Current Datetime: {current_dt_str}
- Current Date (Today): {today_iso}
- Day of Week: {weekday}
- Monday of This Week: {monday_iso}
- 7 Days Ago: {seven_days_ago_iso}
- 10 Days Ago: {ten_days_ago_iso}
- Yesterday: {yesterday_iso}
- User Timezone: {timezone_str}

CURRENT UI STATE SNAPSHOT:
- Current View: {view}
- Current Folder: {folder}
- Active List Filters: {filters_repr}
- Currently Open Email: {open_email_repr}
- Active Compose Draft: {draft_repr}

RULES FOR TOOL CALLING:
1. Relative Dates:
   Always resolve relative dates using the exact TEMPORAL CONTEXT above:
   - "today": date_from="{today_iso}", date_to="{today_iso}"
   - "this week": date_from="{monday_iso}", date_to="{today_iso}" (Monday of this week through today)
   - "last 10 days": date_from="{ten_days_ago_iso}", date_to="{today_iso}"
   - "last 7 days": date_from="{seven_days_ago_iso}", date_to="{today_iso}"
   - "yesterday": date_from="{yesterday_iso}", date_to="{yesterday_iso}"

2. Search and Display (Scenario B & E):
   When the user asks to find, show, or check emails (e.g. "Show me emails from the last 10 days", "Find the email from Sarah about the project update"):
   - Call `search_emails(...)` with the resolved date/sender/keyword filters to retrieve the matching emails.
   - ALSO call `set_filters(...)` with those same filter parameters (`date_from`, `date_to`, `sender`, `keyword`, `unread`) so that the user's MAIN message list immediately refetches and updates, and filter controls and chips reflect the applied filters!
   - In your final response, provide only a one-line summary of what you found. The search results will be shown as preview cards in the chat and in the main list.
   - For filter refinements like "only from Sarah" when filters are already active: call `set_filters(sender="Sarah")`. The app merges this with existing filters.
   - For "clear filters" or "show all emails": call `clear_filters()`.

3. Opening Emails & Disambiguation (Scenario C):
   For "open the latest email from [Person]":
   - Call `search_emails(sender=Person, limit=5)` or `search_emails(keyword=Person, limit=5)` (newest first).
   - If multiple DIFFERENT people/senders match the name (e.g. David Miller and David Smith), DO NOT guess! Ask the user a short clarifying question asking which person they meant.
   - If only one matching sender is found, call `open_email(email_id=...)` to switch the UI to the detail view showing that email.

4. Replying / Forwarding / Context Awareness (Scenario D):
   - For "reply to this" or "reply all":
     - Check `Currently Open Email` in the snapshot above.
     - If NO email is currently open, DO NOT make up an email! Ask the user: "Which email would you like to reply to?"
     - If an email IS open, call `open_compose(mode="reply", reply_to_message_id=openEmail.id)` (or mode="replyAll"). Then call `fill_compose(body=...)` with the reply text.
   - For "forward this to [recipient]":
     - If no email is open, ask which email to forward.
     - If an email is open, call `open_compose(mode="forward", reply_to_message_id=openEmail.id)` and `fill_compose(to=recipient, body=...)`.
   - For "summarize this email":
     - If no email is open, ask which email to summarize.
     - If an email is open, provide a clear, concise summary of its content in chat.

5. Composing and Sending (Scenario A):
   - To draft an email: call `open_compose(mode="new")` and `fill_compose(to=..., subject=..., body=...)`.
   - When the user asks to send: call `propose_send()`.
   - You MUST NEVER claim the email is sent, and you MUST NEVER attempt to send directly. Calling `propose_send()` renders a confirmation card for the human user with Send / Edit / Cancel options.
"""


def _format_sse(event: str, data: dict[str, Any]) -> str:
    """Format SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def execute_server_tool(
    user: User,
    db: Session,
    tool_name: str,
    tool_args: dict[str, Any],
) -> tuple[Any, list[dict[str, Any]] | None]:
    """Execute server-side tools (search_emails, get_email) with Gmail API.

    Returns (tool_result_data, optional_email_cards).
    """
    creds = refresh_credentials_if_needed(user, db)

    if tool_name == "search_emails":
        folder = tool_args.get("folder", "inbox")
        limit = min(int(tool_args.get("limit", 10)), 25)
        filters = Filters(
            folder=folder,
            date_from=tool_args.get("date_from"),
            date_to=tool_args.get("date_to"),
            sender=tool_args.get("sender"),
            keyword=tool_args.get("keyword"),
            unread=tool_args.get("unread"),
            limit=limit,
        )

        res = await asyncio.to_thread(gmail_service.list_messages, creds, filters)
        compact = [
            {
                "id": e.id,
                "from": f"{e.sender.name} <{e.sender.address}>" if e.sender.name else e.sender.address,
                "subject": e.subject,
                "date": e.date,
                "snippet": e.snippet,
                "isRead": e.is_read,
            }
            for e in res.emails
        ]
        cards = [e.model_dump(mode="json") for e in res.emails]
        return compact, cards

    elif tool_name == "get_email":
        msg_id = tool_args.get("id", "")
        detail = await asyncio.to_thread(gmail_service.get_message, creds, msg_id)
        return detail.model_dump(mode="json"), None

    raise ValueError(f"Unknown server tool: {tool_name}")


async def stream_assistant_chat(
    user: User,
    db: Session,
    messages: list[dict[str, Any]],
    ui_state: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """Execute LiteLLM agent loop with tool calling and SSE streaming."""
    # Hop 1: Validate LLM configuration before starting stream
    config_err = validate_llm_config()
    if config_err:
        logger.error("[Assistant] LLM configuration error: %s", config_err)
        yield _format_sse("error", {"message": f"LLM Configuration Error: {config_err}"})
        yield _format_sse("done", {"status": "error"})
        return

    # Ensure provider API keys are populated in environment for LiteLLM
    if settings.gemini_api_key and "GEMINI_API_KEY" not in os.environ:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.gemini_api_key and "VERTEXAI_API_KEY" not in os.environ:
        os.environ["VERTEXAI_API_KEY"] = settings.gemini_api_key
    if settings.openai_api_key and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key and "ANTHROPIC_API_KEY" not in os.environ:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.groq_api_key and "GROQ_API_KEY" not in os.environ:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key

    system_prompt = build_system_prompt(ui_state)
    conversation: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    # Keep only the most recent messages to avoid exceeding Groq's TPM limit.
    recent_messages = messages[-8:]

    for m in recent_messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in {"user", "assistant", "system"}:
            conversation.append({
                "role": role,
                "content": content,
            })

    import litellm

    max_iterations = 6
    iteration = 0

    # In-memory tracking of draft populated during this agent interaction
    accumulated_draft = dict(ui_state.get("currentDraft") or {})

    try:
        while iteration < max_iterations:
            iteration += 1
            logger.info("[Assistant] Iteration %d/%d for user %s", iteration, max_iterations, user.email)

            response = await litellm.acompletion(
                model=settings.llm_model,
                messages=conversation,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                stream=True,
            )

            assistant_text = ""
            tool_calls_map: dict[int, dict[str, Any]] = {}

            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                # Stream text chunks
                if delta.content:
                    assistant_text += delta.content
                    yield _format_sse("text_delta", {"delta": delta.content})

                # Accumulate streamed tool call chunks
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index if tc.index is not None else 0
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {
                                "id": tc.id or f"call_{idx}",
                                "name": tc.function.name if tc.function and tc.function.name else "",
                                "arguments": "",
                            }
                        if tc.id:
                            tool_calls_map[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_map[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_map[idx]["arguments"] += tc.function.arguments

            # If no tool calls, the model has completed its turn
            if not tool_calls_map:
                break

            # Build assistant message with tool calls for history
            assistant_msg_tool_calls = []
            for idx in sorted(tool_calls_map.keys()):
                tc_data = tool_calls_map[idx]
                assistant_msg_tool_calls.append({
                    "id": tc_data["id"],
                    "type": "function",
                    "function": {
                        "name": tc_data["name"],
                        "arguments": tc_data["arguments"],
                    },
                })

            conversation.append({
                "role": "assistant",
                "content": assistant_text or None,
                "tool_calls": assistant_msg_tool_calls,
            })

            # Execute each tool call
            for tc_data in assistant_msg_tool_calls:
                call_id = tc_data["id"]
                fn_name = tc_data["function"]["name"]
                raw_args = tc_data["function"]["arguments"]

                try:
                    args = json.loads(raw_args) if raw_args else {}
                except Exception:
                    args = {}

                logger.info("[Assistant] Model invoked tool '%s' with args: %s", fn_name, args)

                # Inform client of tool execution
                yield _format_sse("tool_call", {"name": fn_name, "args": args})

                # Validate arguments with Pydantic
                try:
                    validate_tool_args(fn_name, args)
                except Exception as val_err:
                    logger.warning("[Assistant] Tool validation failed for %s: %s", fn_name, val_err)
                    yield _format_sse("error", {"message": f"Invalid arguments for {fn_name}: {val_err}"})
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps({"error": str(val_err)}),
                    })
                    continue

                # Track draft parameters if compose action
                if fn_name == "fill_compose":
                    if args.get("to") is not None:
                        accumulated_draft["to"] = args["to"]
                    if args.get("cc") is not None:
                        accumulated_draft["cc"] = args["cc"]
                    if args.get("subject") is not None:
                        accumulated_draft["subject"] = args["subject"]
                    if args.get("body") is not None:
                        accumulated_draft["body"] = args["body"]
                elif fn_name == "open_compose":
                    if args.get("mode") is not None:
                        accumulated_draft["mode"] = args["mode"]

                if fn_name in SERVER_TOOLS:
                    try:
                        result_data, cards = await execute_server_tool(user, db, fn_name, args)
                        if cards:
                            yield _format_sse("email_cards", {"cards": cards})

                        conversation.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": json.dumps(result_data),
                        })
                    except Exception as err:
                        logger.error("[Assistant] Server tool %s error: %s", fn_name, err)
                        conversation.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": json.dumps({"error": str(err)}),
                        })

                elif fn_name in UI_TOOLS:
                    # Emit UI action event to client
                    yield _format_sse("ui_action", {"action": fn_name, "params": args})

                    # If propose_send, emit confirm_send payload using updated draft details
                    if fn_name == "propose_send":
                        if args.get("to"):
                            accumulated_draft["to"] = args["to"]
                        if args.get("subject"):
                            accumulated_draft["subject"] = args["subject"]
                        if args.get("body"):
                            accumulated_draft["body"] = args["body"]

                        body_text = accumulated_draft.get("body", "")
                        body_preview = body_text[:300] + ("..." if len(body_text) > 300 else "")
                        yield _format_sse("confirm_send", {
                            "to": accumulated_draft.get("to", ""),
                            "subject": accumulated_draft.get("subject", "(No subject)"),
                            "bodyPreview": body_preview,
                        })

                    # Feed applied status back to model so loop continues
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps({"status": "applied"}),
                    })

        yield _format_sse("done", {"status": "complete"})

    except Exception as e:
        logger.error("[Assistant] Error in stream_assistant_chat: %s", e)
        yield _format_sse("error", {"message": f"Assistant error: {str(e)}"})
        yield _format_sse("done", {"status": "error"})
