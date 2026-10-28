from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Freshness, WarningCategory, enum_column


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(sa.ForeignKey("medication_lists.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    kb_version: Mapped[str] = mapped_column(sa.String(20))
    # analysis.freshness (Appendix A.2, SAF-08)
    freshness: Mapped[Freshness] = mapped_column(enum_column(Freshness, "freshness"), default=Freshness.CURRENT)

    medication_list: Mapped["MedicationList"] = relationship(back_populates="analyses")  # noqa: F821
    warnings: Mapped[list["AnalysisWarning"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", passive_deletes=True
    )


class AnalysisWarning(Base):
    """The "Warning" entity of Table 5.1, stored in table ``warnings``.

    The Python class is called AnalysisWarning only to avoid clashing with Python's built-in Warning.
    """

    __tablename__ = "warnings"
    __table_args__ = (sa.CheckConstraint("score >= 0 AND score <= 100", name="score_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(sa.ForeignKey("analysis_results.id", ondelete="CASCADE"), index=True)
    category: Mapped[WarningCategory] = mapped_column(enum_column(WarningCategory, "warning_category"))
    # rule_code of the KB rule that produced the warning (e.g. "DDI-0001", "CI-AGE-CLONAZEPAM").
    # Duplicate warnings, which come from no KB row, use a fixed code such as "DUP-SAME".
    rule_reference: Mapped[str] = mapped_column(sa.String(50))
    related_medications: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    score: Mapped[int]
    score_factors: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(sa.Text)

    analysis: Mapped[AnalysisResult] = relationship(back_populates="warnings")
