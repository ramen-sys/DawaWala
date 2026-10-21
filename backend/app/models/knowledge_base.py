"""Knowledge-base entities of SRS Table 5.1: Medication, Drug Interaction, Contraindication, Cascade Rule."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import Severity, enum_column


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    standard_name: Mapped[str] = mapped_column(sa.String(150), unique=True, index=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(sa.String(150)), default=list, server_default="{}")
    drug_class: Mapped[str | None] = mapped_column(sa.String(100), index=True)
    medication_info: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class DrugInteraction(Base):
    __tablename__ = "drug_interactions"
    __table_args__ = (
        sa.UniqueConstraint("drug_a_id", "drug_b_id", name="uq_drug_interactions_pair"),
        sa.CheckConstraint("drug_a_id < drug_b_id", name="ordered_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    drug_a_id: Mapped[int] = mapped_column(sa.ForeignKey("medications.id", ondelete="CASCADE"), index=True)
    drug_b_id: Mapped[int] = mapped_column(sa.ForeignKey("medications.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(sa.Text)
    severity: Mapped[Severity] = mapped_column(enum_column(Severity, "severity"))
    relevant_risk_factors: Mapped[list[str]] = mapped_column(
        ARRAY(sa.String(50)), default=list, server_default="{}"
    )

    drug_a: Mapped[Medication] = relationship(foreign_keys=[drug_a_id])
    drug_b: Mapped[Medication] = relationship(foreign_keys=[drug_b_id])


class Contraindication(Base):
    __tablename__ = "contraindications"
    __table_args__ = (
        sa.UniqueConstraint("medication_id", "patient_condition", name="uq_contraindications_med_condition"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    medication_id: Mapped[int] = mapped_column(sa.ForeignKey("medications.id", ondelete="CASCADE"), index=True)
    # "<factor_type>:<factor_value>", matching the Risk Factor entity, e.g. "age_range:under_18".
    patient_condition: Mapped[str] = mapped_column(sa.String(100))
    description: Mapped[str] = mapped_column(sa.Text)
    severity: Mapped[Severity] = mapped_column(enum_column(Severity, "severity"))

    medication: Mapped[Medication] = relationship()


class CascadeRule(Base):
    __tablename__ = "cascade_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Medication IDs; arrays because a rule can have several triggering / downstream medications.
    triggering_medications: Mapped[list[int]] = mapped_column(ARRAY(sa.Integer))
    symptom_pattern: Mapped[str] = mapped_column(sa.String(255))
    downstream_medications: Mapped[list[int]] = mapped_column(ARRAY(sa.Integer))
    description: Mapped[str] = mapped_column(sa.Text)
