"""Gmail API service layer.

All Gmail API interactions live here. The module is intentionally stateless —
callers pass in Credentials. This makes it trivial to test with mock creds.

Key design choices:
  - List views use format=METADATA for speed (no body download for lists)
  - Detail view fully parses multipart MIME including base64url and charsets
  - Send uses base64url-encoded raw MIME with correct threading headers
  - Rate-limit errors from Google are surfaced as 429 HTTPExceptions
"""
from __future__ import annotations

import base64
import email as email_lib
import email.header
import email.utils
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from fastapi import HTTPException, status
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.schemas.email import (
    Attachment,
    EmailAddress,
    EmailDetail,
    EmailListResponse,
    EmailSummary,
    SendEmailRequest,
    ThreadMessage,
    ThreadResponse,
)
from app.schemas.filters import Filters
from app.services.query_builder import build_gmail_query

# Headers to fetch for metadata-only list requests
_METADATA_HEADERS = ["From", "To", "Cc", "Subject", "Date", "Message-ID"]


# ── Internal helpers ─────────────────────────────────────────────────────────

def _gmail_service(credentials: Credentials):
    """Build and return a Gmail API service client."""
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _handle_http_error(error: HttpError) -> None:
    """Convert Google API HttpErrors to FastAPI HTTPExceptions."""
    code = error.resp.status
    if code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credentials expired. Please re-authenticate.",
        )
    if code == 403:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient Gmail permissions.",
        )
    if code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Gmail API rate limit reached. Try again later.",
        )
    if code == 404:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message or thread not found.",
        )
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Gmail API error: {error}",
    )


def _decode_header_value(raw: str) -> str:
    """Decode RFC 2047 encoded header (e.g., =?UTF-8?b?...?=)."""
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    decoded_parts: list[str] = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def _parse_address_header(raw: str) -> list[EmailAddress]:
    """Parse a From/To/Cc header value into a list of EmailAddress objects."""
    if not raw:
        return []
    addresses = []
    for name, addr in email.utils.getaddresses([raw]):
        addresses.append(EmailAddress(name=_decode_header_value(name), address=addr))
    return addresses


def _get_header(headers: list[dict], name: str) -> str:
    """Extract a specific header value from the Gmail message headers list."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def _decode_base64url(data: str) -> bytes:
    """Decode base64url-encoded data (Gmail uses URL-safe base64 without padding)."""
    # Re-add stripped padding
    data = data.replace("-", "+").replace("_", "/")
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.b64decode(data)


def _extract_parts(
    payload: dict,
    html_parts: list[str],
    plain_parts: list[str],
    attachments: list[Attachment],
) -> None:
    """Recursively walk MIME payload tree to extract body and attachments."""
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})

    if mime_type == "text/html":
        data = body.get("data", "")
        if data:
            html_parts.append(_decode_base64url(data).decode("utf-8", errors="replace"))
    elif mime_type == "text/plain":
        data = body.get("data", "")
        if data:
            plain_parts.append(_decode_base64url(data).decode("utf-8", errors="replace"))
    elif mime_type.startswith("multipart/"):
        for part in payload.get("parts", []):
            _extract_parts(part, html_parts, plain_parts, attachments)
    else:
        # Treat as attachment if it has a filename or attachment body
        filename = payload.get("filename", "")
        attachment_id = body.get("attachmentId", "")
        if filename or attachment_id:
            attachments.append(
                Attachment(
                    attachment_id=attachment_id,
                    filename=filename or "attachment",
                    mime_type=mime_type,
                    size=body.get("size", 0),
                )
            )


def _parse_email_summary(msg: dict) -> EmailSummary:
    """Parse a metadata-format Gmail message into an EmailSummary."""
    headers = msg.get("payload", {}).get("headers", [])
    label_ids = msg.get("labelIds", [])

    from_header = _get_header(headers, "From")
    senders = _parse_address_header(from_header)
    sender = senders[0] if senders else EmailAddress()

    to_header = _get_header(headers, "To")
    to_list = _parse_address_header(to_header)

    date_str = _get_header(headers, "Date")
    # Convert RFC 2822 date to ISO 8601
    try:
        parsed_date = email.utils.parsedate_to_datetime(date_str)
        iso_date = parsed_date.isoformat()
    except Exception:
        iso_date = date_str

    return EmailSummary(
        id=msg["id"],
        threadId=msg.get("threadId", ""),
        sender=sender,
        to=to_list,
        subject=_decode_header_value(_get_header(headers, "Subject")),
        snippet=msg.get("snippet", ""),
        date=iso_date,
        is_read="UNREAD" not in label_ids,
    )


def _parse_email_detail(msg: dict) -> EmailDetail:
    """Parse a full Gmail message into an EmailDetail."""
    headers = msg.get("payload", {}).get("headers", [])
    label_ids = msg.get("labelIds", [])

    from_header = _get_header(headers, "From")
    senders = _parse_address_header(from_header)
    sender = senders[0] if senders else EmailAddress()

    to_list = _parse_address_header(_get_header(headers, "To"))
    cc_list = _parse_address_header(_get_header(headers, "Cc"))
    reply_to_list = _parse_address_header(_get_header(headers, "Reply-To"))
    reply_to = reply_to_list[0] if reply_to_list else None

    date_str = _get_header(headers, "Date")
    try:
        parsed_date = email.utils.parsedate_to_datetime(date_str)
        iso_date = parsed_date.isoformat()
    except Exception:
        iso_date = date_str

    html_parts: list[str] = []
    plain_parts: list[str] = []
    attachments: list[Attachment] = []
    _extract_parts(msg.get("payload", {}), html_parts, plain_parts, attachments)

    return EmailDetail(
        id=msg["id"],
        threadId=msg.get("threadId", ""),
        sender=sender,
        to=to_list,
        cc=cc_list,
        reply_to=reply_to,
        subject=_decode_header_value(_get_header(headers, "Subject")),
        date=iso_date,
        body_html="\n".join(html_parts),
        body_plain="\n".join(plain_parts),
        snippet=msg.get("snippet", ""),
        attachments=attachments,
        is_read="UNREAD" not in label_ids,
    )


# ── Public API functions ──────────────────────────────────────────────────────

def list_messages(credentials: Credentials, filters: Filters) -> EmailListResponse:
    """List messages for the given filters.

    Uses messages.list to get IDs then fetches each with format=METADATA
    for performance (no body download).
    """
    try:
        service = _gmail_service(credentials)
        query = build_gmail_query(filters)

        result = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=filters.limit,
                pageToken=filters.page_token or None,
            )
            .execute()
        )

        messages_raw = result.get("messages", [])
        next_page_token = result.get("nextPageToken")
        result_size_estimate = result.get("resultSizeEstimate", 0)

        if not messages_raw:
            return EmailListResponse(
                emails=[],
                next_page_token=None,
                result_size_estimate=0,
            )

        # Batch fetch metadata for each message
        emails: list[EmailSummary] = []
        batch = service.new_batch_http_request()

        fetched: dict[str, dict] = {}

        def _callback(request_id: str, response: Any, exception: Any) -> None:
            if exception is None and response:
                fetched[request_id] = response

        for msg_stub in messages_raw:
            msg_id = msg_stub["id"]
            batch.add(
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=_METADATA_HEADERS,
                ),
                callback=_callback,
                request_id=msg_id,
            )

        batch.execute()

        # Preserve order from messages_raw
        for msg_stub in messages_raw:
            msg_id = msg_stub["id"]
            if msg_id in fetched:
                emails.append(_parse_email_summary(fetched[msg_id]))

        return EmailListResponse(
            emails=emails,
            next_page_token=next_page_token,
            result_size_estimate=result_size_estimate,
        )

    except HttpError as e:
        _handle_http_error(e)
        raise  # unreachable but satisfies type checker


def get_message(credentials: Credentials, message_id: str) -> EmailDetail:
    """Fetch a single message with full MIME body."""
    try:
        service = _gmail_service(credentials)
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        return _parse_email_detail(msg)
    except HttpError as e:
        _handle_http_error(e)
        raise


def send_message(
    credentials: Credentials, req: SendEmailRequest, sender_email: str
) -> dict:
    """Compose and send a MIME email, threading it correctly for replies."""
    try:
        service = _gmail_service(credentials)

        # Build MIME message
        msg = MIMEMultipart("alternative")
        msg["From"] = sender_email
        msg["To"] = ", ".join(req.to)
        if req.cc:
            msg["Cc"] = ", ".join(req.cc)
        msg["Subject"] = req.subject

        # Threading headers for replies
        if req.reply_to_message_id:
            msg["In-Reply-To"] = req.reply_to_message_id
            msg["References"] = req.reply_to_message_id

        # Plain-text fallback (strip tags)
        plain_body = re.sub(r"<[^>]+>", "", req.body)
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(req.body, "html", "utf-8"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        body: dict[str, Any] = {"raw": raw}
        if req.thread_id:
            body["threadId"] = req.thread_id

        sent = service.users().messages().send(userId="me", body=body).execute()
        return sent

    except HttpError as e:
        _handle_http_error(e)
        raise


def modify_labels(
    credentials: Credentials,
    message_id: str,
    add_labels: list[str],
    remove_labels: list[str],
) -> dict:
    """Add/remove Gmail labels from a message."""
    try:
        service = _gmail_service(credentials)
        return (
            service.users()
            .messages()
            .modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": add_labels, "removeLabelIds": remove_labels},
            )
            .execute()
        )
    except HttpError as e:
        _handle_http_error(e)
        raise


def get_thread(credentials: Credentials, thread_id: str) -> ThreadResponse:
    """Fetch all messages in a thread."""
    try:
        service = _gmail_service(credentials)
        thread = (
            service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )

        messages_raw = thread.get("messages", [])
        thread_messages: list[ThreadMessage] = []
        subject = ""

        for msg in messages_raw:
            detail = _parse_email_detail(msg)
            if not subject:
                subject = detail.subject
            thread_messages.append(
                ThreadMessage(
                    id=detail.id,
                    sender=detail.sender,
                    date=detail.date,
                    snippet=detail.snippet,
                    body_html=detail.body_html,
                    body_plain=detail.body_plain,
                    is_read=detail.is_read,
                )
            )

        return ThreadResponse(
            thread_id=thread_id,
            subject=subject,
            messages=thread_messages,
        )

    except HttpError as e:
        _handle_http_error(e)
        raise


def get_user_profile(credentials: Credentials) -> dict:
    """Get the user's Gmail profile including current historyId."""
    try:
        service = _gmail_service(credentials)
        return service.users().getProfile(userId="me").execute()
    except HttpError as e:
        _handle_http_error(e)
        raise


def watch_inbox(credentials: Credentials, topic_name: str) -> dict:
    """Register Gmail push notifications on INBOX to Cloud Pub/Sub topic."""
    try:
        service = _gmail_service(credentials)
        return (
            service.users()
            .watch(userId="me", body={"topicName": topic_name, "labelIds": ["INBOX"]})
            .execute()
        )
    except HttpError as e:
        _handle_http_error(e)
        raise


def stop_watch(credentials: Credentials) -> None:
    """Stop Gmail push notifications for user."""
    try:
        service = _gmail_service(credentials)
        service.users().stop(userId="me").execute()
    except HttpError as e:
        _handle_http_error(e)
        raise


def list_history(
    credentials: Credentials,
    start_history_id: str,
) -> tuple[list[EmailSummary], str]:
    """Fetch new messages added since start_history_id.

    Returns (new_emails, latest_history_id).
    """
    try:
        service = _gmail_service(credentials)
        history_resp = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
            )
            .execute()
        )

        latest_history_id = str(history_resp.get("historyId", start_history_id))
        history_records = history_resp.get("history", [])

        # Collect new message IDs
        message_ids: list[str] = []
        for record in history_records:
            for msg_added in record.get("messagesAdded", []):
                msg = msg_added.get("message", {})
                msg_id = msg.get("id")
                if msg_id and msg_id not in message_ids:
                    message_ids.append(msg_id)

        if not message_ids:
            return [], latest_history_id

        # Fetch metadata for the new messages
        emails: list[EmailSummary] = []
        batch = service.new_batch_http_request()
        fetched: dict[str, dict] = {}

        def _callback(request_id: str, response: Any, exception: Any) -> None:
            if exception is None and response:
                fetched[request_id] = response

        for msg_id in message_ids:
            batch.add(
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=_METADATA_HEADERS,
                ),
                callback=_callback,
                request_id=msg_id,
            )
        batch.execute()

        for msg_id in message_ids:
            if msg_id in fetched:
                emails.append(_parse_email_summary(fetched[msg_id]))

        return emails, latest_history_id
    except HttpError as e:
        if e.resp.status == 404:
            profile = get_user_profile(credentials)
            return [], str(profile.get("historyId", start_history_id))
        _handle_http_error(e)
        raise

