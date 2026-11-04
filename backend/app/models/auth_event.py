from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AuthEventType, enum_column


class AuthEvent(Base):
    """SEC-10: one authentication event or authorization failure.

    Holds only who (user ID), what (event type), when and from where (IP address) - never
    passwords, tokens, e-mail addresses or medication data. Rows older than
    AUTH_LOG_RETENTION_DAYS (90) are removed by ``auth_event_service.purge_old_events``.
    """

    __tablename__ = "auth_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL for failed logins with an unknown e-mail. ON DELETE SET NULL keeps the security
    # history after an account is deleted (SEC-08) without keeping a link to the person.
    user_id: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[AuthEventType] = mapped_column(enum_column(AuthEventType, "auth_event_type"))
    ip_address: Mapped[str | None] = mapped_column(sa.String(45))  # 45 chars fits an IPv6 address
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), index=True
    )
