from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ConfirmationFlag,
    ConfirmationStatus,
    FactorType,
    ListSource,
    OcrStatus,
    enum_column,
)


class MedicationList(Base):
    __tablename__ = "medication_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[ListSource] = mapped_column(enum_column(ListSource, "list_source"), default=ListSource.MANUAL)
    confirmation_status: Mapped[ConfirmationStatus] = mapped_column(
        enum_column(ConfirmationStatus, "confirmation_status"), default=ConfirmationStatus.DRAFT
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())

    user: Mapped["User"] = relationship(back_populates="medication_lists")  # noqa: F821
    items: Mapped[list["MedicationListItem"]] = relationship(
        back_populates="medication_list",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MedicationListItem.id",
    )
    images: Mapped[list["PrescriptionImage"]] = relationship(
        back_populates="medication_list", cascade="all, delete-orphan", passive_deletes=True
    )
    risk_factors: Mapped[list["RiskFactor"]] = relationship(
        back_populates="medication_list", cascade="all, delete-orphan", passive_deletes=True
    )
    analyses: Mapped[list["AnalysisResult"]] = relationship(  # noqa: F821
        back_populates="medication_list", cascade="all, delete-orphan", passive_deletes=True
    )


class MedicationListItem(Base):
    __tablename__ = "medication_list_items"
    __table_args__ = (
        sa.CheckConstraint("match_score IS NULL OR (match_score >= 0 AND match_score <= 100)", name="match_score_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(sa.ForeignKey("medication_lists.id", ondelete="CASCADE"), index=True)
    medication_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("medications.id", ondelete="SET NULL"), index=True
    )
    raw_text: Mapped[str] = mapped_column(sa.String(100))
    match_score: Mapped[int | None]
    confirmation_flag: Mapped[ConfirmationFlag] = mapped_column(
        enum_column(ConfirmationFlag, "confirmation_flag"), default=ConfirmationFlag.UNRESOLVED
    )

    medication_list: Mapped[MedicationList] = relationship(back_populates="items")
    medication: Mapped["Medication | None"] = relationship()  # noqa: F821


class PrescriptionImage(Base):
    __tablename__ = "prescription_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(sa.ForeignKey("medication_lists.id", ondelete="CASCADE"), index=True)
    file_reference: Mapped[str] = mapped_column(sa.String(255), unique=True)
    uploaded_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    ocr_status: Mapped[OcrStatus] = mapped_column(enum_column(OcrStatus, "ocr_status"), default=OcrStatus.PENDING)

    medication_list: Mapped[MedicationList] = relationship(back_populates="images")
    extraction: Mapped["OcrExtractionResult | None"] = relationship(
        back_populates="image", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class OcrExtractionResult(Base):
    __tablename__ = "ocr_extraction_results"
    __table_args__ = (
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 100)", name="confidence_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(
        sa.ForeignKey("prescription_images.id", ondelete="CASCADE"), unique=True
    )
    raw_text: Mapped[str] = mapped_column(sa.Text, default="")
    candidates: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default="[]")
    confidence: Mapped[float | None]

    image: Mapped[PrescriptionImage] = relationship(back_populates="extraction")


class RiskFactor(Base):
    __tablename__ = "risk_factors"
    __table_args__ = (sa.UniqueConstraint("list_id", "factor_type", name="uq_risk_factors_list_factor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("users.id", ondelete="CASCADE"), index=True)
    list_id: Mapped[int] = mapped_column(sa.ForeignKey("medication_lists.id", ondelete="CASCADE"), index=True)
    factor_type: Mapped[FactorType] = mapped_column(enum_column(FactorType, "factor_type"))
    factor_value: Mapped[str] = mapped_column(sa.String(50), default="unknown")

    medication_list: Mapped[MedicationList] = relationship(back_populates="risk_factors")
