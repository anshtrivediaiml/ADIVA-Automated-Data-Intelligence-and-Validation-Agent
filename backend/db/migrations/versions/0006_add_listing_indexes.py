"""add listing indexes for jobs and reviews

Revision ID: 0006_add_listing_indexes
Revises: 0005_add_recovery_attempts
Create Date: 2026-04-04
"""

from alembic import op


revision = "0006_add_listing_indexes"
down_revision = "0005_add_recovery_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_documents_user_created_at",
        "documents",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_extractions_user_created_at",
        "extractions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_extractions_user_status_created_at",
        "extractions",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_extraction_results_extraction_id",
        "extraction_results",
        ["extraction_id"],
        unique=False,
    )
    op.create_index(
        "ix_extraction_outputs_extraction_id",
        "extraction_outputs",
        ["extraction_id"],
        unique=False,
    )
    op.create_index(
        "ix_validation_reports_extraction_id",
        "validation_reports",
        ["extraction_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_cases_user_created_at",
        "review_cases",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_review_cases_user_status_created_at",
        "review_cases",
        ["user_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_review_cases_user_status_created_at", table_name="review_cases")
    op.drop_index("ix_review_cases_user_created_at", table_name="review_cases")
    op.drop_index("ix_validation_reports_extraction_id", table_name="validation_reports")
    op.drop_index("ix_extraction_outputs_extraction_id", table_name="extraction_outputs")
    op.drop_index("ix_extraction_results_extraction_id", table_name="extraction_results")
    op.drop_index("ix_extractions_user_status_created_at", table_name="extractions")
    op.drop_index("ix_extractions_user_created_at", table_name="extractions")
    op.drop_index("ix_documents_user_created_at", table_name="documents")
