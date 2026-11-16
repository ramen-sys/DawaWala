"""risk factors as factor:value tokens on interaction, contraindication and cascade rules

* drug_interactions.relevant_risk_factors: factor types (e.g. "age_range") -> "factor:value"
  tokens (e.g. "age_range:65_plus"), so the +5 per matching factor in Table 5.2 can be applied
  only when the patient has the value that actually raises the risk.
* contraindications.relevant_risk_factors: new column, same format, so a contraindication can
  also earn the patient-factor modifier (e.g. metformin + impaired kidneys, worse at 65+).
* cascade_rules.relevant_risk_factors: new column, same format (most cascades matter more at 65+).

Revision ID: e7a1c2f40b19
Revises: bc4d4a7d2b45
Create Date: 2026-11-04 10:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e7a1c2f40b19'
down_revision: Union[str, Sequence[str], None] = 'bc4d4a7d2b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of app.models.enums.risk_factor_tokens() at the time of this migration.
TOKENS = (
    "age_range:under_18", "age_range:18_64", "age_range:65_plus",
    "kidney_function:normal", "kidney_function:impaired",
    "liver_function:normal", "liver_function:impaired",
)
FACTOR_TYPES = ("age_range", "kidney_function", "liver_function", "other")


def _array_check(column: str, allowed: Sequence[str]) -> str:
    return f"{column} <@ ARRAY[{', '.join(repr(v) for v in allowed)}]::varchar[]"


def upgrade() -> None:
    # drug_interactions is empty at this revision, but clear any factor-type-only entries anyway
    # so the new constraint can be created.
    op.drop_constraint(op.f("ck_drug_interactions_relevant_risk_factors_valid"), "drug_interactions", type_="check")
    op.execute("UPDATE drug_interactions SET relevant_risk_factors = '{}' "
               "WHERE NOT (" + _array_check("relevant_risk_factors", TOKENS) + ")")
    op.create_check_constraint(op.f("ck_drug_interactions_relevant_risk_factors_valid"), "drug_interactions",
                               _array_check("relevant_risk_factors", TOKENS))

    for table in ('contraindications', 'cascade_rules'):
        op.add_column(table, sa.Column('relevant_risk_factors', postgresql.ARRAY(sa.String(length=50)),
                                       server_default='{}', nullable=False))
        op.create_check_constraint(op.f(f"ck_{table}_relevant_risk_factors_valid"), table,
                                   _array_check("relevant_risk_factors", TOKENS))


def downgrade() -> None:
    for table in ('cascade_rules', 'contraindications'):
        op.drop_constraint(op.f(f"ck_{table}_relevant_risk_factors_valid"), table, type_="check")
        op.drop_column(table, 'relevant_risk_factors')

    op.drop_constraint(op.f("ck_drug_interactions_relevant_risk_factors_valid"), "drug_interactions", type_="check")
    # "age_range:65_plus" -> "age_range"
    op.execute("UPDATE drug_interactions SET relevant_risk_factors = ARRAY("
               "SELECT DISTINCT split_part(t, ':', 1) FROM unnest(relevant_risk_factors) AS t)::varchar[]")
    op.create_check_constraint(op.f("ck_drug_interactions_relevant_risk_factors_valid"), "drug_interactions",
                               _array_check("relevant_risk_factors", FACTOR_TYPES))
