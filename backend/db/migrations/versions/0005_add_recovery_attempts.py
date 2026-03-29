"""add recovery attempts table

Revision ID: 0005_add_recovery_attempts
Revises: 0004_add_review_foundation
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_add_recovery_attempts"
down_revision = "0004_add_review_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recovery_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("extractions.id"), nullable=False),
        sa.Column("review_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_cases.id"), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="shadow"),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="started"),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("weak_fields_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason_codes_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("input_summary_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_summary_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("improvement_score", sa.Float(), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("extraction_id", "attempt_number", name="uq_recovery_attempts_extraction_attempt"),
    )
    op.create_index("ix_recovery_attempts_status", "recovery_attempts", ["status"], unique=False)
    op.create_index(
        "ix_recovery_attempts_extraction_created_at",
        "recovery_attempts",
        ["extraction_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_recovery_attempts_extraction_created_at", table_name="recovery_attempts")
    op.drop_index("ix_recovery_attempts_status", table_name="recovery_attempts")
    op.drop_table("recovery_attempts")
