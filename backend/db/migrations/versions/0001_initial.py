"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False, server_default="user"),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("storage_uri", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_documents_checksum", "documents", ["checksum"], unique=False)

    op.create_table(
        "extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_extractions_status_created_at", "extractions", ["status", "created_at"], unique=False)

    op.create_table(
        "extraction_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("extractions.id"), nullable=False),
        sa.Column("document_type", sa.String(length=128), nullable=True),
        sa.Column("structured_data_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("detected_language", sa.String(length=64), nullable=True),
        sa.Column("metadata_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_extraction_results_document_type", "extraction_results", ["document_type"], unique=False)
    op.create_index(
        "ix_extraction_results_structured_data_gin",
        "extraction_results",
        ["structured_data_jsonb"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "extraction_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("extractions.id"), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "validation_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("extractions.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("issues_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("metadata_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("validation_reports")
    op.drop_table("extraction_outputs")
    op.drop_index("ix_extraction_results_structured_data_gin", table_name="extraction_results")
    op.drop_index("ix_extraction_results_document_type", table_name="extraction_results")
    op.drop_table("extraction_results")
    op.drop_index("ix_extractions_status_created_at", table_name="extractions")
    op.drop_table("extractions")
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
