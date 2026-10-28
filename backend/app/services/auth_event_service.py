"""SEC-10: record authentication events and authorization failures, and delete them after 90 days."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import log_auth_event
from app.models import AuthEvent
from app.models.enums import AuthEventType


def record_event(
    db: Session, event: AuthEventType, user_id: int | None, ip: str | None, *, commit: bool = True
) -> None:
    """Save one event in ``auth_events`` and also write it to the rotating auth.log file.

    Pass ``commit=False`` when the caller is about to commit its own changes in the same
    transaction (for example the failed-login counter), so both are saved together.
    """
    db.add(AuthEvent(user_id=user_id, event_type=event, ip_address=ip))
    if commit:
        db.commit()
    log_auth_event(event.value, user_id, ip)


def purge_old_events(db: Session, now: datetime | None = None) -> int:
    """Delete events older than AUTH_LOG_RETENTION_DAYS. Returns how many rows were removed."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.AUTH_LOG_RETENTION_DAYS)
    result = db.execute(delete(AuthEvent).where(AuthEvent.created_at < cutoff))
    db.commit()
    return result.rowcount
