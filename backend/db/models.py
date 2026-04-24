from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(64), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    role = Column(String(64), nullable=False, default="user")
    hashed_password = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    filename = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    checksum = Column(String(128), nullable=True, index=True)
    storage_uri = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_documents_user_created_at", "user_id", "created_at"),
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status = Column(String(32), nullable=False, default="queued")
    current_stage = Column(String(64), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    model_name = Column(String(128), nullable=True)
    model_version = Column(String(64), nullable=True)
    prompt_version = Column(String(64), nullable=True)
    review_required = Column(Boolean, nullable=False, default=False)
    validation_decision = Column(String(32), nullable=True)
    batch_id = Column(String(128), nullable=True, index=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_extractions_status_created_at", "status", "created_at"),
        Index("ix_extractions_user_created_at", "user_id", "created_at"),
        Index("ix_extractions_user_status_created_at", "user_id", "status", "created_at"),
    )


class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=False)
    document_type = Column(String(128), nullable=True, index=True)
    structured_data_jsonb = Column(JSONB, nullable=True)
    confidence_jsonb = Column(JSONB, nullable=True)
    detected_language = Column(String(64), nullable=True)
    metadata_jsonb = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_extraction_results_extraction_id", "extraction_id"),
    )


class ExtractionOutput(Base):
    __tablename__ = "extraction_outputs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=False)
    format = Column(String(16), nullable=False)
    storage_uri = Column(Text, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_extraction_outputs_extraction_id", "extraction_id"),
    )


class ValidationReport(Base):
    __tablename__ = "validation_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    issues_jsonb = Column(JSONB, nullable=True)
    quality_score = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_validation_reports_extraction_id", "extraction_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(128), nullable=False)
    resource_type = Column(String(128), nullable=False)
    resource_id = Column(String(128), nullable=True)
    metadata_jsonb = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReviewCase(Base):
    __tablename__ = "review_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    document_type = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="open", index=True)
    priority = Column(String(32), nullable=False, default="normal")
    source_job_status = Column(String(32), nullable=False)
    validation_decision = Column(String(32), nullable=True)
    review_reason_codes_jsonb = Column(JSONB, nullable=True)
    review_summary_jsonb = Column(JSONB, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("extraction_id", name="uq_review_cases_extraction_id"),
        Index("ix_review_cases_status_created_at", "status", "created_at"),
        Index("ix_review_cases_user_created_at", "user_id", "created_at"),
        Index("ix_review_cases_user_status_created_at", "user_id", "status", "created_at"),
    )


class ReviewFieldItem(Base):
    __tablename__ = "review_field_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_case_id = Column(UUID(as_uuid=True), ForeignKey("review_cases.id"), nullable=False)
    field_path = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="open", index=True)
    reason_code = Column(String(64), nullable=False)
    is_critical = Column(Boolean, nullable=False, default=False)
    field_confidence = Column(Float, nullable=True)
    original_value_jsonb = Column(JSONB, nullable=True)
    proposed_value_jsonb = Column(JSONB, nullable=True)
    final_value_jsonb = Column(JSONB, nullable=True)
    evidence_text = Column(Text, nullable=True)
    validation_message = Column(Text, nullable=True)
    recovery_attempt_number = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("review_case_id", "field_path", name="uq_review_field_items_case_field"),
        Index("ix_review_field_items_case_status", "review_case_id", "status"),
    )


class FieldCorrection(Base):
    __tablename__ = "field_corrections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_case_id = Column(UUID(as_uuid=True), ForeignKey("review_cases.id"), nullable=False)
    review_field_item_id = Column(UUID(as_uuid=True), ForeignKey("review_field_items.id"), nullable=False)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=False)
    corrected_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    field_path = Column(String(255), nullable=False)
    correction_source = Column(String(32), nullable=False)
    old_value_jsonb = Column(JSONB, nullable=True)
    new_value_jsonb = Column(JSONB, nullable=True)
    correction_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=False)
    review_case_id = Column(UUID(as_uuid=True), ForeignKey("review_cases.id"), nullable=True)
    attempt_number = Column(Integer, nullable=False)
    mode = Column(String(32), nullable=False, default="shadow")
    strategy = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="started", index=True)
    model_name = Column(String(128), nullable=True)
    weak_fields_jsonb = Column(JSONB, nullable=True)
    reason_codes_jsonb = Column(JSONB, nullable=True)
    input_summary_jsonb = Column(JSONB, nullable=True)
    output_summary_jsonb = Column(JSONB, nullable=True)
    improvement_score = Column(Float, nullable=True)
    accepted = Column(Boolean, nullable=True)
    failure_reason = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("extraction_id", "attempt_number", name="uq_recovery_attempts_extraction_attempt"),
        Index("ix_recovery_attempts_extraction_created_at", "extraction_id", "created_at"),
    )
