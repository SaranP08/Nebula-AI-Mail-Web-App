"""SQLAlchemy database setup for SQLite.

Usage:
    from app.database import SessionLocal, engine, Base
    Base.metadata.create_all(bind=engine)  # called on startup
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# connect_args is needed for SQLite to allow the same connection
# to be used in multiple threads (FastAPI runs in a thread pool).
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a database session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
