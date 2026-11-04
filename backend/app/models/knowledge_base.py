"""Knowledge-base entities of SRS Table 5.1: Medication, Drug Interaction, Contraindication, Cascade Rule.

Conventions shared by every KB rule table (Drug Interaction, Contraindication, Cascade Rule):

* ``rule_code`` - stable, human-readable identifier of the rule (for example ``DDI-0001``,
  ``CI-AGE-CLONAZEPAM``, ``CAS-0001``). A warning stores it in ``warnings.rule_reference`` so
  every warning can be traced back to the rule that produced it (QA-EXP-04, FR-13).
* ``source`` - where the rule came from (dataset / reference), required by SRS Section 5.3.

The knowledge-base version itself is global (``settings.KB_VERSION``) and is stored on every
analysis result, so it is not repeated on each row.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    FactorType,
    Severity,
    enum_column,
    factor_pair_check_sql,
    factor_type_array_check_sql,
)


class Medication(Base):
    """A standard (generic) medication. Brand names and other spellings live in ``medication_aliases``."""

    __tablename__ = "medications"
    __table_args__ = (
        # Trigram index so fuzzy matching (FR-6) and type-ahead (FR-3, PERF-03) stay fast.
        sa.Index(
            "ix_medications_standard_name_trgm",
            "standard_name",
            postgresql_using="gin",
            postgresql_ops={"standard_name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    standard_name: Mapped[str] = mapped_column(sa.String(150), unique=True, index=True)
    # Indexed because the duplication check (FR-9) groups medications by class.
    drug_class: Mapped[str | None] = mapped_column(sa.String(100), index=True)
    medication_info: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    source: Mapped[str] = mapped_column(sa.String(255))
    # Optional code from an external vocabulary such as ATC (SRS Section 5.4).
    external_code: Mapped[str | None] = mapped_column(sa.String(50))

    aliases: Mapped[list["MedicationAlias"]] = relationship(
        back_populates="medication",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MedicationAlias.alias",
    )

    @property
    def alias_names(self) -> list[str]:
        """Plain list of alias strings, e.g. ["Calpol", "Panadol"]."""
        return [a.alias for a in self.aliases]


class MedicationAlias(Base):
    """One brand name / alternative name of a medication (Table 5.1 "Aliases/brand names").

    Stored as rows instead of an array so each name can be indexed with pg_trgm and looked up
    directly, which the fuzzy matcher (FR-6) needs to meet PERF-03.
    """

    __tablename__ = "medication_aliases"
    __table_args__ = (
        sa.UniqueConstraint("medication_id", "alias", name="uq_medication_aliases_med_alias"),
        sa.Index(
            "ix_medication_aliases_alias_trgm",
            "alias",
            postgresql_using="gin",
            postgresql_ops={"alias": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    medication_id: Mapped[int] = mapped_column(sa.ForeignKey("medications.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(sa.String(150))

    medication: Mapped[Medication] = relationship(back_populates="aliases")


class DrugInteraction(Base):
    """An interaction between two medications. Pairs are stored once, with drug_a_id < drug_b_id."""

    __tablename__ = "drug_interactions"
    __table_args__ = (
        sa.UniqueConstraint("drug_a_id", "drug_b_id", name="uq_drug_interactions_pair"),
        sa.CheckConstraint("drug_a_id < drug_b_id", name="ordered_pair"),
        # Every entry must be a FactorType value, so a typo cannot disable the patient-factor modifier (Table 5.2).
        sa.CheckConstraint(factor_type_array_check_sql("relevant_risk_factors"), name="relevant_risk_factors_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(sa.String(50), unique=True)
    drug_a_id: Mapped[int] = mapped_column(sa.ForeignKey("medications.id", ondelete="CASCADE"), index=True)
    drug_b_id: Mapped[int] = mapped_column(sa.ForeignKey("medications.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(sa.Text)
    severity: Mapped[Severity] = mapped_column(enum_column(Severity, "severity"))
    # Factor types (e.g. ["age_range", "kidney_function"]) that make this interaction riskier.
    relevant_risk_factors: Mapped[list[FactorType]] = mapped_column(
        ARRAY(sa.String(50)), default=list, server_default="{}"
    )
    source: Mapped[str] = mapped_column(sa.String(255))

    drug_a: Mapped[Medication] = relationship(foreign_keys=[drug_a_id])
    drug_b: Mapped[Medication] = relationship(foreign_keys=[drug_b_id])


class Contraindication(Base):
    """A medication that should be avoided for a patient factor, e.g. Clonazepam for age_range = under_18.

    The patient condition from Table 5.1 is split into ``factor_type`` + ``factor_value`` using the same
    values as ``risk_factors``, so FR-10 can match them with a simple equality join.
    """

    __tablename__ = "contraindications"
    __table_args__ = (
        sa.UniqueConstraint(
            "medication_id", "factor_type", "factor_value", name="uq_contraindications_med_factor"
        ),
        sa.CheckConstraint(factor_pair_check_sql(), name="factor_value_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(sa.String(50), unique=True)
    medication_id: Mapped[int] = mapped_column(sa.ForeignKey("medications.id", ondelete="CASCADE"), index=True)
    factor_type: Mapped[FactorType] = mapped_column(enum_column(FactorType, "factor_type"))
    factor_value: Mapped[str] = mapped_column(sa.String(50))
    description: Mapped[str] = mapped_column(sa.Text)
    severity: Mapped[Severity] = mapped_column(enum_column(Severity, "severity"))
    source: Mapped[str] = mapped_column(sa.String(255))

    medication: Mapped[Medication] = relationship()


# Join tables for Cascade Rule <-> Medication. Real foreign keys keep referential integrity
# (a deleted medication cannot leave a dangling ID), and FR-12 can read the triggering and
# downstream sets separately.
cascade_rule_triggers = sa.Table(
    "cascade_rule_triggers",
    Base.metadata,
    sa.Column("rule_id", sa.ForeignKey("cascade_rules.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("medication_id", sa.ForeignKey("medications.id", ondelete="CASCADE"), primary_key=True, index=True),
)

cascade_rule_downstream = sa.Table(
    "cascade_rule_downstream",
    Base.metadata,
    sa.Column("rule_id", sa.ForeignKey("cascade_rules.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("medication_id", sa.ForeignKey("medications.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class CascadeRule(Base):
    """A prescribing-cascade pattern: a triggering medication causes a symptom that is then
    treated with a downstream medication (FR-12)."""

    __tablename__ = "cascade_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(sa.String(50), unique=True)
    symptom_pattern: Mapped[str] = mapped_column(sa.String(255))
    description: Mapped[str] = mapped_column(sa.Text)
    source: Mapped[str] = mapped_column(sa.String(255))

    triggering_medications: Mapped[list[Medication]] = relationship(
        secondary=cascade_rule_triggers, order_by=Medication.id
    )
    downstream_medications: Mapped[list[Medication]] = relationship(
        secondary=cascade_rule_downstream, order_by=Medication.id
    )
