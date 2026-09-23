"""FastAPI application entrypoint.

In development:
  uvicorn app.main:app --reload --port 8000

In production:
  The built frontend (frontend/dist/) is served as static files from this app.
  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import assistant, auth, emails, sync
from app.config import settings
from app.database import Base, engine
from app.models import User  # noqa: F401 — registers the ORM model
from app.services.sync_service import daily_watch_renewal_loop, poll_sync_loop

# Create all tables on startup
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Background startup and shutdown tasks."""
    background_tasks: list[asyncio.Task] = []

    # Start daily Gmail watch renewal task
    background_tasks.append(asyncio.create_task(daily_watch_renewal_loop()))

    # Start local polling fallback if configured
    if settings.sync_mode.lower() == "poll":
        background_tasks.append(asyncio.create_task(poll_sync_loop()))

    yield

    # Cancel background tasks cleanly on shutdown
    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)


app = FastAPI(
    title="AI-Powered Mail App",
    description="Gmail client API with Google OAuth2 and AI assistant, powered by FastAPI.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
cors_origins = [settings.frontend_url]
if settings.base_url and settings.base_url not in cors_origins:
    cors_origins.append(settings.base_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,  # required for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(sync.router)
app.include_router(assistant.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health() -> dict:
    from sqlalchemy import text
    from app.database import SessionLocal

    db_ok = True
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    finally:
        db.close()

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "service": "mail-api",
        "database": "connected" if db_ok else "error",
        "sync_mode": settings.sync_mode,
        "llm_model": settings.llm_model,
    }


# ── Production static file serving ───────────────────────────────────────────
# Resolve frontend dist directory
_DIST = None
candidate_dirs = [
    Path(settings.frontend_dist_dir) if settings.frontend_dist_dir else None,
    Path("/app/frontend/dist"),
    Path(__file__).parent.parent.parent / "frontend" / "dist",
    Path("frontend/dist"),
    Path("../frontend/dist"),
]

for candidate in candidate_dirs:
    if candidate and candidate.exists():
        _DIST = candidate
        break

if _DIST and _DIST.exists():
    # Mount assets (JS, CSS, etc.)
    if (_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        """Serve the SPA index.html for all non-API routes (client-side routing)."""
        # Don't intercept /api/*, /auth/*, /webhooks/*, or /health routes
        if (
            full_path.startswith("api/")
            or full_path.startswith("auth/")
            or full_path.startswith("webhooks/")
            or full_path == "health"
        ):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        index = _DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Frontend index.html not found")
