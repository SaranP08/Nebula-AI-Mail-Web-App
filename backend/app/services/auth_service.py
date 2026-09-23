"""Google OAuth2 web flow + session management.

Responsibilities:
  - Build the Google authorization URL
  - Exchange the code for tokens
  - Store / update tokens in SQLite
  - Sign and verify the HTTP-only session cookie with itsdangerous
  - Auto-refresh expired access tokens
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

# ── Cookie name ──────────────────────────────────────────────────────────────
SESSION_COOKIE = "mail_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

# ── Serializer for signing the session cookie ────────────────────────────────
_serializer = URLSafeTimedSerializer(settings.secret_key, salt="mail-session")


# ── OAuth2 Flow factory ──────────────────────────────────────────────────────

def _build_flow() -> Flow:
    """Create a google-auth-oauthlib Flow from env config."""
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=settings.google_scopes,
        redirect_uri=settings.google_redirect_uri,
    )
    return flow


def get_authorization_url() -> tuple[str, str]:
    """Return (auth_url, state) to redirect the user to Google."""
    flow = _build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",   # force consent to always get a refresh_token
    )
    return auth_url, state


def exchange_code(code: str, state: str) -> Credentials:
    """Exchange the authorization code for OAuth2 Credentials."""
    flow = _build_flow()
    flow.fetch_token(code=code)
    return flow.credentials


# ── User upsert ──────────────────────────────────────────────────────────────

def _get_google_user_info(credentials: Credentials) -> dict:
    """Fetch the Google profile for the authenticated user."""
    service = build("oauth2", "v2", credentials=credentials)
    return service.userinfo().get().execute()


def upsert_user(credentials: Credentials, db: Session) -> User:
    """Create or update a User record from fresh Google credentials."""
    user_info = _get_google_user_info(credentials)
    google_id = user_info["id"]

    user = db.get(User, google_id)
    if user is None:
        user = User(id=google_id)
        db.add(user)

    user.email = user_info.get("email", "")
    user.name = user_info.get("name", "")
    user.picture = user_info.get("picture", "")
    user.access_token = credentials.token
    user.refresh_token = credentials.refresh_token or user.refresh_token
    if credentials.expiry:
        user.token_expiry = to_naive_utc(credentials.expiry)

    db.commit()
    db.refresh(user)
    return user


# ── Session cookie helpers ────────────────────────────────────────────────────

def create_session_cookie(response: Response, user_id: str) -> None:
    """Sign the user_id and set it as an HTTP-only cookie."""
    token = _serializer.dumps({"uid": user_id})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_same_site,  # type: ignore[arg-type]
        max_age=SESSION_MAX_AGE,
        path="/",
    )


def delete_session_cookie(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE, path="/")


def _verify_session_token(token: str) -> Optional[str]:
    """Return the user_id from the signed token, or None if invalid/expired."""
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("uid")
    except (BadSignature, SignatureExpired):
        return None


# ── Helpers & Credentials builder (with auto-refresh) ─────────────────────────

def to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert a datetime to a naive UTC datetime for google-auth compatibility.

    google-auth requires Credentials.expiry to be a naive UTC datetime.
    - If dt is timezone-aware, converts it to UTC and removes tzinfo.
    - If dt is already naive, assumes it represents UTC and returns it as-is.
    - If dt is None, returns None.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_credentials_for_user(user: User) -> Credentials:
    """Build a google.oauth2.credentials.Credentials object for a User.

    The google client library will auto-refresh if the access token is expired
    as long as the refresh_token and client_id/secret are present.
    Ensures expiry is converted to naive UTC to prevent TypeError in google-auth.
    """
    expiry = to_naive_utc(user.token_expiry)

    creds = Credentials(
        token=user.access_token,
        refresh_token=user.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=settings.google_scopes,
        expiry=expiry,
    )
    return creds


def refresh_credentials_if_needed(user: User, db: Session) -> Credentials:
    """Return valid credentials, refreshing and persisting if expired."""
    import google.auth.transport.requests as google_requests

    creds = get_credentials_for_user(user)
    if creds.expired and creds.refresh_token:
        request = google_requests.Request()
        creds.refresh(request)
        # Persist refreshed tokens consistently as naive UTC
        user.access_token = creds.token
        if creds.expiry:
            user.token_expiry = to_naive_utc(creds.expiry)
        db.commit()
    return creds


# ── FastAPI dependency: require authenticated user ────────────────────────────

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — raises 401 if not authenticated."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = _verify_session_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
