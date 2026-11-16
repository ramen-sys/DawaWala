"""SEC-10: authentication and authorization events go to a daily-rotated file kept for 90 days.

Log records carry only the event name, user ID and client IP: never passwords, tokens or medications.
"""

import logging
from logging.handlers import TimedRotatingFileHandler

from app.core.config import settings

auth_logger = logging.getLogger("dawawala.auth")


def configure_logging() -> None:
    if auth_logger.handlers:
        return
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        settings.LOG_DIR / "auth.log",
        when="midnight",
        backupCount=settings.AUTH_LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    auth_logger.addHandler(handler)
    auth_logger.setLevel(logging.INFO)


def log_auth_event(event: str, user_id: int | None, ip: str | None) -> None:
    auth_logger.info("event=%s user_id=%s ip=%s", event, user_id if user_id is not None else "-", ip or "-")
