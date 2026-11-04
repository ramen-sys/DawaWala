"""review fixes: roles, rule codes, aliases table, cascade joins, auth events

* users.role: patient / healthcare_professional -> user / admin (FR-1, Table 5.1).
* medications.aliases array -> medication_aliases table with pg_trgm indexes (FR-6, PERF-03).
* medications.source / external_code (SRS 5.3, 5.4).
* rule_code + source on drug_interactions, contraindications, cascade_rules (QA-EXP-04, SRS 5.3).
* contraindications.patient_condition -> factor_type + factor_value, validated like risk_factors.
* cascade_rules arrays -> cascade_rule_triggers / cascade_rule_downstream join tables with FKs.
* drug_interactions.relevant_risk_factors limited to FactorType values.
* medication_list_items.raw_text -> TEXT; ocr_extraction_results.confidence -> INTEGER.
* auth_events table (SEC-10).

Revision ID: bc4d4a7d2b45
Revises: cd3890861c86
Create Date: 2026-10-22 19:25:57.572934

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.models.enums import (
    AuthEventType,
    FactorType,
    UserRole,
    factor_pair_check_sql,
    factor_type_array_check_sql,
)

revision: str = 'bc4d4a7d2b45'
down_revision: Union[str, Sequence[str], None] = 'cd3890861c86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KAGGLE_SOURCE = "Kaggle: Pakistan Medicines Dataset (muhammadabdullah222), version 3"


def _in_list(column: str, enum_cls) -> str:
    return f"{column} IN ({', '.join(repr(m.value) for m in enum_cls)})"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- users.role: map the old roles onto User / Admin ---
    op.drop_constraint(op.f("ck_users_user_role"), "users", type_="check")
    op.execute("UPDATE users SET role = 'user' WHERE role IN ('patient', 'healthcare_professional')")
    op.create_check_constraint(op.f("ck_users_user_role"), "users", _in_list("role", UserRole))

    # --- auth_events (SEC-10) ---
    op.create_table(
        'auth_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(_in_list("event_type", AuthEventType), name=op.f('ck_auth_events_auth_event_type')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_auth_events_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_events')),
    )
    op.create_index(op.f('ix_auth_events_created_at'), 'auth_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_auth_events_user_id'), 'auth_events', ['user_id'], unique=False)

    # --- medications: source, external_code, aliases table ---
    op.add_column('medications', sa.Column('source', sa.String(length=255), nullable=True))
    op.execute(sa.text("UPDATE medications SET source = :s").bindparams(s=KAGGLE_SOURCE))
    op.alter_column('medications', 'source', nullable=False)
    op.add_column('medications', sa.Column('external_code', sa.String(length=50), nullable=True))
    op.execute("UPDATE medications SET medication_info = medication_info - 'source'")
    op.create_index('ix_medications_standard_name_trgm', 'medications', ['standard_name'], unique=False,
                    postgresql_using='gin', postgresql_ops={'standard_name': 'gin_trgm_ops'})

    op.create_table(
        'medication_aliases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('medication_id', sa.Integer(), nullable=False),
        sa.Column('alias', sa.String(length=150), nullable=False),
        sa.ForeignKeyConstraint(['medication_id'], ['medications.id'],
                                name=op.f('fk_medication_aliases_medication_id_medications'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_medication_aliases')),
        sa.UniqueConstraint('medication_id', 'alias', name='uq_medication_aliases_med_alias'),
    )
    op.create_index('ix_medication_aliases_alias_trgm', 'medication_aliases', ['alias'], unique=False,
                    postgresql_using='gin', postgresql_ops={'alias': 'gin_trgm_ops'})
    op.create_index(op.f('ix_medication_aliases_medication_id'), 'medication_aliases', ['medication_id'], unique=False)
    op.execute(
        "INSERT INTO medication_aliases (medication_id, alias) "
        "SELECT DISTINCT id, unnest(aliases) FROM medications"
    )
    op.drop_column('medications', 'aliases')

    # --- drug_interactions: rule_code, source, valid risk factors (table is empty so far) ---
    op.add_column('drug_interactions', sa.Column('rule_code', sa.String(length=50), nullable=False))
    op.add_column('drug_interactions', sa.Column('source', sa.String(length=255), nullable=False))
    op.create_unique_constraint(op.f('uq_drug_interactions_rule_code'), 'drug_interactions', ['rule_code'])
    op.create_check_constraint(op.f("ck_drug_interactions_relevant_risk_factors_valid"), "drug_interactions",
                               factor_type_array_check_sql("relevant_risk_factors"))

    # --- contraindications: "age_range:under_18" -> factor_type + factor_value, plus rule_code/source ---
    op.add_column('contraindications', sa.Column('rule_code', sa.String(length=50), nullable=True))
    op.add_column('contraindications', sa.Column('factor_type', sa.String(length=32), nullable=True))
    op.add_column('contraindications', sa.Column('factor_value', sa.String(length=50), nullable=True))
    op.add_column('contraindications', sa.Column('source', sa.String(length=255), nullable=True))
    op.execute(sa.text(
        "UPDATE contraindications SET "
        "factor_type = split_part(patient_condition, ':', 1), "
        "factor_value = split_part(patient_condition, ':', 2), "
        "rule_code = 'CI-' || id, "  # re-running the importer replaces these with CI-AGE-<NAME> codes
        "source = :s"
    ).bindparams(s=KAGGLE_SOURCE))
    for column in ('rule_code', 'factor_type', 'factor_value', 'source'):
        op.alter_column('contraindications', column, nullable=False)
    op.drop_constraint(op.f('uq_contraindications_med_condition'), 'contraindications', type_='unique')
    op.drop_column('contraindications', 'patient_condition')
    op.create_unique_constraint('uq_contraindications_med_factor', 'contraindications',
                                ['medication_id', 'factor_type', 'factor_value'])
    op.create_unique_constraint(op.f('uq_contraindications_rule_code'), 'contraindications', ['rule_code'])
    op.create_check_constraint(op.f("ck_contraindications_factor_type"), "contraindications", _in_list("factor_type", FactorType))
    op.create_check_constraint(op.f("ck_contraindications_factor_value_valid"), "contraindications", factor_pair_check_sql())

    # --- risk_factors: same allowed (type, value) pairs ---
    op.create_check_constraint(op.f("ck_risk_factors_factor_value_valid"), "risk_factors", factor_pair_check_sql())

    # --- cascade_rules: arrays -> join tables with real FKs (table is empty so far) ---
    op.add_column('cascade_rules', sa.Column('rule_code', sa.String(length=50), nullable=False))
    op.add_column('cascade_rules', sa.Column('source', sa.String(length=255), nullable=False))
    op.create_unique_constraint(op.f('uq_cascade_rules_rule_code'), 'cascade_rules', ['rule_code'])
    op.drop_column('cascade_rules', 'downstream_medications')
    op.drop_column('cascade_rules', 'triggering_medications')
    for table in ('cascade_rule_triggers', 'cascade_rule_downstream'):
        op.create_table(
            table,
            sa.Column('rule_id', sa.Integer(), nullable=False),
            sa.Column('medication_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['medication_id'], ['medications.id'],
                                    name=op.f(f'fk_{table}_medication_id_medications'), ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['rule_id'], ['cascade_rules.id'],
                                    name=op.f(f'fk_{table}_rule_id_cascade_rules'), ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('rule_id', 'medication_id', name=op.f(f'pk_{table}')),
        )
        op.create_index(op.f(f'ix_{table}_medication_id'), table, ['medication_id'], unique=False)

    # --- list items / OCR ---
    op.alter_column('medication_list_items', 'raw_text', existing_type=sa.VARCHAR(length=100),
                    type_=sa.Text(), existing_nullable=False)
    op.alter_column('ocr_extraction_results', 'confidence', existing_type=sa.DOUBLE_PRECISION(precision=53),
                    type_=sa.Integer(), existing_nullable=True, postgresql_using='round(confidence)::integer')


def downgrade() -> None:
    op.alter_column('ocr_extraction_results', 'confidence', existing_type=sa.Integer(),
                    type_=sa.DOUBLE_PRECISION(precision=53), existing_nullable=True)
    op.alter_column('medication_list_items', 'raw_text', existing_type=sa.Text(),
                    type_=sa.VARCHAR(length=100), existing_nullable=False)

    for table in ('cascade_rule_downstream', 'cascade_rule_triggers'):
        op.drop_index(op.f(f'ix_{table}_medication_id'), table_name=table)
        op.drop_table(table)
    op.add_column('cascade_rules', sa.Column('triggering_medications', postgresql.ARRAY(sa.INTEGER()),
                                             server_default='{}', nullable=False))
    op.add_column('cascade_rules', sa.Column('downstream_medications', postgresql.ARRAY(sa.INTEGER()),
                                             server_default='{}', nullable=False))
    op.drop_constraint(op.f('uq_cascade_rules_rule_code'), 'cascade_rules', type_='unique')
    op.drop_column('cascade_rules', 'source')
    op.drop_column('cascade_rules', 'rule_code')

    op.drop_constraint(op.f("ck_risk_factors_factor_value_valid"), 'risk_factors', type_='check')

    op.add_column('contraindications', sa.Column('patient_condition', sa.VARCHAR(length=100), nullable=True))
    op.execute("UPDATE contraindications SET patient_condition = factor_type || ':' || factor_value")
    op.alter_column('contraindications', 'patient_condition', nullable=False)
    op.drop_constraint(op.f("ck_contraindications_factor_value_valid"), 'contraindications', type_='check')
    op.drop_constraint(op.f("ck_contraindications_factor_type"), 'contraindications', type_='check')
    op.drop_constraint(op.f('uq_contraindications_rule_code'), 'contraindications', type_='unique')
    op.drop_constraint('uq_contraindications_med_factor', 'contraindications', type_='unique')
    op.create_unique_constraint(op.f('uq_contraindications_med_condition'), 'contraindications',
                                ['medication_id', 'patient_condition'])
    for column in ('source', 'factor_value', 'factor_type', 'rule_code'):
        op.drop_column('contraindications', column)

    op.drop_constraint(op.f("ck_drug_interactions_relevant_risk_factors_valid"), 'drug_interactions', type_='check')
    op.drop_constraint(op.f('uq_drug_interactions_rule_code'), 'drug_interactions', type_='unique')
    op.drop_column('drug_interactions', 'source')
    op.drop_column('drug_interactions', 'rule_code')

    op.add_column('medications', sa.Column('aliases', postgresql.ARRAY(sa.VARCHAR(length=150)),
                                           server_default='{}', nullable=False))
    op.execute(
        "UPDATE medications m SET aliases = coalesce("
        "(SELECT array_agg(a.alias ORDER BY a.alias) FROM medication_aliases a WHERE a.medication_id = m.id), '{}')"
    )
    op.drop_index(op.f('ix_medication_aliases_medication_id'), table_name='medication_aliases')
    op.drop_index('ix_medication_aliases_alias_trgm', table_name='medication_aliases')
    op.drop_table('medication_aliases')
    op.drop_index('ix_medications_standard_name_trgm', table_name='medications')
    op.drop_column('medications', 'external_code')
    op.drop_column('medications', 'source')

    op.drop_index(op.f('ix_auth_events_user_id'), table_name='auth_events')
    op.drop_index(op.f('ix_auth_events_created_at'), table_name='auth_events')
    op.drop_table('auth_events')

    op.drop_constraint(op.f("ck_users_user_role"), "users", type_="check")
    op.execute("UPDATE users SET role = 'patient' WHERE role IN ('user', 'admin')")
    op.create_check_constraint(op.f("ck_users_user_role"), "users", "role IN ('patient', 'healthcare_professional')")
