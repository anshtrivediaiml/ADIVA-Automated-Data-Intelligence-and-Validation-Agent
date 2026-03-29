"""add orchestration fields to extractions

Revision ID: 0003_add_orchestration_fields
Revises: 0002_add_username
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_orchestration_fields"
down_revision = "0002_add_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("extractions", sa.Column("current_stage", sa.String(length=64), nullable=True))
    op.add_column("extractions", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "extractions",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column("extractions", sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("extractions", sa.Column("validation_decision", sa.String(length=32), nullable=True))
    op.add_column("extractions", sa.Column("batch_id", sa.String(length=128), nullable=True))
    op.add_column("extractions", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_index("ix_extractions_batch_id", "extractions", ["batch_id"], unique=False)
    op.create_index("ix_extractions_idempotency_key", "extractions", ["idempotency_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_extractions_idempotency_key", table_name="extractions")
    op.drop_index("ix_extractions_batch_id", table_name="extractions")
    op.drop_column("extractions", "idempotency_key")
    op.drop_column("extractions", "batch_id")
    op.drop_column("extractions", "validation_decision")
    op.drop_column("extractions", "review_required")
    op.drop_column("extractions", "submitted_at")
    op.drop_column("extractions", "retry_count")
    op.drop_column("extractions", "current_stage")
