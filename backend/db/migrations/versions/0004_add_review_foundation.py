"""add review foundation tables

Revision ID: 0004_add_review_foundation
Revises: 0003_add_orchestration_fields
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0004_add_review_foundation"
down_revision = "0003_add_orchestration_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("extractions.id"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("document_type", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("source_job_status", sa.String(length=32), nullable=False),
        sa.Column("validation_decision", sa.String(length=32), nullable=True),
        sa.Column("review_reason_codes_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("review_summary_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("extraction_id", name="uq_review_cases_extraction_id"),
    )
    op.create_index("ix_review_cases_document_type", "review_cases", ["document_type"], unique=False)
    op.create_index("ix_review_cases_status", "review_cases", ["status"], unique=False)
    op.create_index("ix_review_cases_status_created_at", "review_cases", ["status", "created_at"], unique=False)

    op.create_table(
        "review_field_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("review_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_cases.id"), nullable=False),
        sa.Column("field_path", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("is_critical", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("field_confidence", sa.Float(), nullable=True),
        sa.Column("original_value_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("proposed_value_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("final_value_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("recovery_attempt_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("review_case_id", "field_path", name="uq_review_field_items_case_field"),
    )
    op.create_index("ix_review_field_items_status", "review_field_items", ["status"], unique=False)
    op.create_index("ix_review_field_items_case_status", "review_field_items", ["review_case_id", "status"], unique=False)

    op.create_table(
        "field_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("review_case_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_cases.id"), nullable=False),
        sa.Column("review_field_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_field_items.id"), nullable=False),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("extractions.id"), nullable=False),
        sa.Column("corrected_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("field_path", sa.String(length=255), nullable=False),
        sa.Column("correction_source", sa.String(length=32), nullable=False),
        sa.Column("old_value_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_field_corrections_extraction_id", "field_corrections", ["extraction_id"], unique=False)
    op.create_index("ix_field_corrections_review_case_id", "field_corrections", ["review_case_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_field_corrections_review_case_id", table_name="field_corrections")
    op.drop_index("ix_field_corrections_extraction_id", table_name="field_corrections")
    op.drop_table("field_corrections")

    op.drop_index("ix_review_field_items_case_status", table_name="review_field_items")
    op.drop_index("ix_review_field_items_status", table_name="review_field_items")
    op.drop_table("review_field_items")

    op.drop_index("ix_review_cases_status_created_at", table_name="review_cases")
    op.drop_index("ix_review_cases_status", table_name="review_cases")
    op.drop_index("ix_review_cases_document_type", table_name="review_cases")
    op.drop_table("review_cases")
