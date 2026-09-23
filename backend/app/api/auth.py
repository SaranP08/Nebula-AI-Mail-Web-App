"""Authentication API routes.

GET  /auth/login     → Redirect to Google OAuth consent screen
GET  /auth/callback  → Exchange code for tokens, set session cookie
GET  /auth/me        → Return current user info (requires auth)
POST /auth/logout    → Clear session cookie
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    picture: str


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    """Redirect the user to Google's OAuth2 consent screen."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
        )
    auth_url, state = auth_service.get_authorization_url()
    # Store state in session cookie for CSRF validation on callback
    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_same_site,  # type: ignore[arg-type]
        max_age=600,  # 10 minutes
        path="/",
    )
    return response


@router.get("/callback")
def callback(
    code: str,
    state: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle the Google OAuth2 callback."""
    # Validate state to prevent CSRF
    stored_state = request.cookies.get("oauth_state")
    if stored_state != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state mismatch — possible CSRF attack.",
        )

    try:
        credentials = auth_service.exchange_code(code=code, state=state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange authorization code: {exc}",
        ) from exc

    user = auth_service.upsert_user(credentials, db)

    # Automatically set up Gmail watch on login if topic configured, or initialize historyId
    try:
        from app.services.sync_service import setup_watch
        setup_watch(db, user)
    except Exception as e:
        # Don't fail the login flow if watch setup encounters an error
        pass

    redirect = RedirectResponse(url=settings.frontend_url, status_code=302)
    auth_service.create_session_cookie(redirect, user.id)
    # Clear the temporary oauth_state cookie
    redirect.delete_cookie(key="oauth_state", path="/")
    return redirect


@router.get("/me", response_model=UserResponse)
def me(
    request: Request,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    user = auth_service.get_current_user(request=request, db=db)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name or "",
        picture=user.picture or "",
    )


@router.post("/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie and log the user out."""
    auth_service.delete_session_cookie(response)
    return {"message": "Logged out successfully"}
