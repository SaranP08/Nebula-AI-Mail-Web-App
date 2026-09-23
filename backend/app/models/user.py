"""SQLAlchemy User model — stores Google OAuth tokens per user."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    # Google sub (subject) is used as the primary key
    id: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    picture: Mapped[str] = mapped_column(Text, nullable=True)

    # OAuth tokens
    access_token: Mapped[str] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Gmail push sync / history tracking
    last_history_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    watch_expiration: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"
