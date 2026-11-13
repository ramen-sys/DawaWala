"""analysis results storage for FR-15: not analysed / not assessed, risk factors, KB date, band, rank, details

Revision ID: f3b8d1a6c2e4
Revises: e7a1c2f40b19
Create Date: 2026-11-11

Additive only: every new column has a server default, so existing rows stay valid.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3b8d1a6c2e4"
down_revision: Union[str, Sequence[str], None] = "e7a1c2f40b19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analysis_results", sa.Column("kb_updated_on", sa.String(10), nullable=False, server_default=""))
    op.add_column("analysis_results", sa.Column(
        "not_analysed", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("analysis_results", sa.Column(
        "not_assessed", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("analysis_results", sa.Column(
        "risk_factors", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("warnings", sa.Column(
        "severity_band",
        sa.Enum("low", "moderate", "high", "critical", name="severity_band",
                native_enum=False, create_constraint=True, length=32),
        nullable=False, server_default="low"))
    op.add_column("warnings", sa.Column("rank", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("warnings", sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("warnings", "details")
    op.drop_column("warnings", "rank")
    op.drop_column("warnings", "severity_band")  # its CHECK constraint is dropped with it
    op.drop_column("analysis_results", "risk_factors")
    op.drop_column("analysis_results", "not_assessed")
    op.drop_column("analysis_results", "not_analysed")
    op.drop_column("analysis_results", "kb_updated_on")
