"""Gmail synchronization service.

Handles:
- users.watch setup and automatic renewal
- Pub/Sub webhook message decoding and history.list processing
- Live channel broadcasting for new emails
- Local polling fallback (SYNC_MODE=poll) every 15 seconds
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.services.auth_service import refresh_credentials_if_needed, to_naive_utc
from app.services.broadcaster import broadcaster
from app.services import gmail_service

logger = logging.getLogger(__name__)


def setup_watch(db: Session, user: User) -> dict[str, Any]:
    """Call users.watch on the INBOX label for a user and record expiration and historyId.

    Requires settings.gmail_pubsub_topic to be configured.
    """
    if not settings.gmail_pubsub_topic:
        logger.warning("GMAIL_PUBSUB_TOPIC not configured; skipping users.watch.")
        # Even if topic is not configured, initialize historyId if missing
        if not user.last_history_id:
            try:
                creds = refresh_credentials_if_needed(user, db)
                profile = gmail_service.get_user_profile(creds)
                user.last_history_id = str(profile.get("historyId", ""))
                db.commit()
            except Exception as e:
                logger.error("Failed to initialize historyId for %s: %s", user.email, e)
        return {"status": "skipped", "reason": "no_topic"}

    try:
        creds = refresh_credentials_if_needed(user, db)
        watch_res = gmail_service.watch_inbox(creds, settings.gmail_pubsub_topic)
        user.last_history_id = str(watch_res.get("historyId", user.last_history_id or ""))

        # Expiration is returned as a millisecond timestamp string
        exp_ms = watch_res.get("expiration")
        if exp_ms:
            user.watch_expiration = to_naive_utc(
                datetime.fromtimestamp(int(exp_ms) / 1000, tz=timezone.utc)
            )

        db.commit()
        logger.info(
            "Successfully set up Gmail watch for %s. HistoryId: %s, Expiration: %s",
            user.email,
            user.last_history_id,
            user.watch_expiration,
        )
        return {
            "status": "active",
            "historyId": user.last_history_id,
            "expiration": user.watch_expiration.isoformat() if user.watch_expiration else None,
        }
    except Exception as e:
        logger.error("Error setting up Gmail watch for user %s: %s", user.email, e)
        raise


async def process_history_update(
    user_email: str,
    new_history_id: str | None = None,
) -> int:
    """Process a history update for a user.

    Fetches new messages added since the user's stored last_history_id,
    broadcasts new_mail events to the user's live stream, and updates last_history_id.
    Returns the number of new emails published.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            logger.warning("No user found with email %s for history update.", user_email)
            return 0

        creds = refresh_credentials_if_needed(user, db)

        # If user has no starting historyId, record current and exit
        if not user.last_history_id:
            profile = gmail_service.get_user_profile(creds)
            user.last_history_id = str(profile.get("historyId", new_history_id or ""))
            db.commit()
            logger.info("Initialized baseline historyId %s for %s", user.last_history_id, user.email)
            return 0

        start_history_id = user.last_history_id
        # Run Google API call in thread pool to avoid blocking async loop
        new_emails, latest_history_id = await asyncio.to_thread(
            gmail_service.list_history, creds, start_history_id
        )

        user.last_history_id = latest_history_id or new_history_id or user.last_history_id
        db.commit()

        # Publish each new email to user's live SSE channel
        count = 0
        for email in new_emails:
            payload = email.model_dump(mode="json")
            await broadcaster.publish(user.id, "new_mail", {"email": payload})
            count += 1

        logger.info(
            "Processed history update for %s: found %d new messages. New historyId: %s",
            user.email,
            count,
            user.last_history_id,
        )
        return count
    except Exception as e:
        logger.error("Error processing history update for %s: %s", user_email, e)
        return 0
    finally:
        db.close()


async def daily_watch_renewal_loop() -> None:
    """Background loop that checks watches once a day and renews any expiring soon."""
    logger.info("Starting daily Gmail watch renewal task.")
    while True:
        try:
            db = SessionLocal()
            users = db.query(User).filter(User.refresh_token.isnot(None)).all()
            now_naive = to_naive_utc(datetime.now(timezone.utc))

            for user in users:
                # Renew if never watched or expiring within 48 hours
                watch_exp = to_naive_utc(user.watch_expiration)
                needs_renewal = (
                    watch_exp is None
                    or (watch_exp - now_naive).total_seconds() < 48 * 3600
                )
                if needs_renewal and settings.gmail_pubsub_topic:
                    logger.info("Renewing Gmail watch for user %s", user.email)
                    try:
                        setup_watch(db, user)
                    except Exception as e:
                        logger.warning("Failed to renew watch for %s: %s", user.email, e)
            db.close()
        except asyncio.CancelledError:
            logger.info("Watch renewal loop cancelled.")
            break
        except Exception as e:
            logger.error("Error in watch renewal loop: %s", e)

        # Sleep for 24 hours (86400 seconds)
        await asyncio.sleep(86400)


async def poll_sync_loop() -> None:
    """Local dev fallback: polls history.list every 15s instead of Pub/Sub."""
    logger.info("Starting local polling sync loop (interval: 15s).")
    while True:
        try:
            db = SessionLocal()
            users = db.query(User).filter(User.refresh_token.isnot(None)).all()
            user_emails = [u.email for u in users]
            db.close()

            for email in user_emails:
                try:
                    await process_history_update(email)
                except Exception as e:
                    logger.debug("Error in poll sync for %s: %s", email, e)
        except asyncio.CancelledError:
            logger.info("Poll sync loop cancelled.")
            break
        except Exception as e:
            logger.error("Error in poll sync loop: %s", e)

        await asyncio.sleep(15)
