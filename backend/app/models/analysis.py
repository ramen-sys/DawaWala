from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Freshness, SeverityBand, WarningCategory, enum_column


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(sa.ForeignKey("medication_lists.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    kb_version: Mapped[str] = mapped_column(sa.String(20))
    # Knowledge-base last-update date the analysis ran against (SAF-07), ISO "YYYY-MM-DD".
    kb_updated_on: Mapped[str] = mapped_column(sa.String(10), default="", server_default="")
    # FR-15 / SAF-03: items the engine could not check ("Not analysed") and contraindication
    # checks skipped because a patient factor was unknown ("Not assessed"). Stored so a reopened
    # analysis shows exactly what was shown when it ran.
    not_analysed: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default="[]")
    not_assessed: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default="[]")
    # Patient factors used for this run (FR-14); the list's factors may change later.
    risk_factors: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    # analysis.freshness (Appendix A.2, SAF-08)
    freshness: Mapped[Freshness] = mapped_column(enum_column(Freshness, "freshness"), default=Freshness.CURRENT)

    medication_list: Mapped["MedicationList"] = relationship(back_populates="analyses")  # noqa: F821
    warnings: Mapped[list["AnalysisWarning"]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AnalysisWarning.rank",
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
    # rule_code of the KB rule that produced the warning (e.g. "INT-0001", "CI-AGE-CLONAZEPAM",
    # "INT-0100/5-12" for a class-level rule). Duplicate warnings, which come from no KB row, use
    # the engine's codes: "DUP-EXACT", "DUP-INGREDIENT:<ingredient>", "DUP-CLASS:<class>".
    rule_reference: Mapped[str] = mapped_column(sa.String(50))
    related_medications: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    score: Mapped[int]
    score_factors: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    # warning.severity_band (Appendix A.2), stored because the band thresholds are configurable.
    severity_band: Mapped[SeverityBand] = mapped_column(
        enum_column(SeverityBand, "severity_band"), default=SeverityBand.LOW, server_default=SeverityBand.LOW.value
    )
    # 0-based position in the FR-11 order (score, then category, then name), so history reopens identically.
    rank: Mapped[int] = mapped_column(default=0, server_default="0")
    # Rule severity, relevant/matched patient factors and the engine's details (via, trigger/downstream, ...).
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    explanation: Mapped[str] = mapped_column(sa.Text)

    analysis: Mapped[AnalysisResult] = relationship(back_populates="warnings")
