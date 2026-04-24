"""
Pydantic Response Models

Define response schemas for API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class ExtractionResponse(BaseModel):
    """Response for single document extraction"""
    status: str = Field(..., description="Status of extraction (success/error)")
    extraction_id: str = Field(..., description="Unique extraction identifier")
    document_type: Optional[str] = Field(None, description="Detected document type")
    confidence: Optional[float] = Field(None, description="Overall extraction confidence")
    detected_language: Optional[str] = Field(None, description="Auto-detected document language (English/Hindi/Gujarati)")
    extraction_folder: str = Field(..., description="Path to extraction folder")
    files: Dict[str, str] = Field(default_factory=dict, description="Generated file paths")
    extracted_data: Optional[Dict[str, Any]] = Field(None, description="Complete extracted JSON data")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "extraction_id": "8d4f5a3e-6c7b-4a2a-9c2a-0e8b6b2a9c1f",
                "document_type": "invoice",
                "confidence": 0.885,
                "detected_language": "Hindi",
                "extraction_folder": "outputs/extracted/20260204_180000_invoice",
                "files": {
                    "json": "extraction.json",
                    "csv": "extraction.csv",
                    "excel": "extraction.xlsx",
                    "html": "extraction.html"
                },
                "processing_time": 8.5
            }
        }


class BatchResponse(BaseModel):
    """Response for batch extraction"""
    status: str
    batch_id: str
    batch_folder: str
    total_documents: int
    processed: int
    failed: int
    results: List[ExtractionResponse]
    processing_time: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "batch_id": "batch_20260204_180000",
                "batch_folder": "outputs/extracted/batch_20260204_180000",
                "total_documents": 3,
                "processed": 3,
                "failed": 0,
                "results": [],
                "processing_time": 25.3
            }
        }


class ExtractionListItem(BaseModel):
    """Single extraction in list"""
    extraction_id: str
    document_type: Optional[str]
    filename: str
    processed_at: str
    confidence: Optional[float]
    status: str


class ExtractionListResponse(BaseModel):
    """Response for listing extractions"""
    total: int
    page: int
    page_size: int
    extractions: List[ExtractionListItem]


class ErrorResponse(BaseModel):
    """Error response"""
    status: str = "error"
    message: str
    detail: Optional[str] = None
    request_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "message": "File upload failed",
                "detail": "File size exceeds maximum allowed size",
                "request_id": "7b1918e905bf43ca8ddadf9da5768307"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    dependencies: Dict[str, str]
    uptime: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "dependencies": {
                    "tesseract": "available",
                    "mistral_ai": "available",
                    "ocr": "ready"
                }
            }
        }


class JobSubmissionResponse(BaseModel):
    """Planned async submission contract for Phase 2 orchestration."""

    job_id: str
    document_id: str
    status: str
    submitted_at: datetime
    status_url: str
    result_url: str


class BatchJobItem(BaseModel):
    """Single job created from a batch submission."""

    job_id: str
    filename: str
    status: str
    status_url: str


class BatchSubmissionResponse(BaseModel):
    """Planned async batch submission contract for Phase 2 orchestration."""

    batch_id: str
    status: str
    total_documents: int
    submitted_at: datetime
    jobs: List[BatchJobItem] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    """Planned status payload for orchestrated processing jobs."""

    job_id: str
    document_id: str
    file_name: Optional[str] = None
    document_type: Optional[str] = None
    ocr_confidence: Optional[float] = None
    overall_confidence: Optional[float] = None
    status: str
    current_stage: Optional[str] = None
    submitted_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    retry_count: int = 0
    review_required: bool = False
    failure_reason: Optional[str] = None
    validation_decision: Optional[str] = None
    validation_summary: Optional[Dict[str, Any]] = None
    review_case_id: Optional[str] = None
    review_status: Optional[str] = None
    review_priority: Optional[str] = None
    review_open_field_count: int = 0
    critical_review_open_field_count: int = 0
    recovery_attempt_count: int = 0
    timings: Dict[str, float] = Field(default_factory=dict)


class JobListResponse(BaseModel):
    """Paginated job listing."""

    total: int
    page: int
    page_size: int
    jobs: List[JobStatusResponse] = Field(default_factory=list)


class JobSummaryResponse(BaseModel):
    """Lightweight job summary for list page headers."""

    generated_at: datetime
    cache_ttl_seconds: float
    total_jobs: int = 0
    active_count: int = 0
    queued_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    needs_review_count: int = 0
    low_confidence_count: int = 0
    failed_count: int = 0


class JobResultResponse(BaseModel):
    """Planned final result contract for async orchestration."""

    job_id: str
    status: str
    document_type: Optional[str] = None
    confidence: Optional[float] = None
    validation_decision: Optional[str] = None
    validation_summary: Optional[Dict[str, Any]] = None
    review_reasons: List[str] = Field(default_factory=list)
    artifacts: Dict[str, str] = Field(default_factory=dict)


class ResultFlaggedFieldResponse(BaseModel):
    """Open flagged field shown alongside a result payload."""

    field_item_id: str
    id: str
    field_path: str
    display_label: str
    label: str
    reason_code: str
    validation_message: str
    message: str
    original_value: Any = None
    proposed_value: Any = None
    evidence_text: Optional[str] = None
    is_critical: bool = False
    priority_score: int = 0


class ResultResponse(BaseModel):
    """Frontend-friendly terminal result payload."""

    job_id: str
    status: str
    file_name: Optional[str] = None
    document_type: Optional[str] = None
    doc_type: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    confidence: Optional[Dict[str, Any]] = None
    detected_language: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    review_required: bool = False
    validation_decision: Optional[str] = None
    validation_summary: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None
    review_case_id: Optional[str] = None
    review_status: Optional[str] = None
    review_priority: Optional[str] = None
    review_open_field_count: int = 0
    critical_review_open_field_count: int = 0
    review_summary: Dict[str, Any] = Field(default_factory=dict)
    recovery_attempt_count: int = 0
    unresolved_review_fields: List[ResultFlaggedFieldResponse] = Field(default_factory=list)
    artifacts: Dict[str, str] = Field(default_factory=dict)


class ReviewFieldItemResponse(BaseModel):
    """Single unresolved or reviewed field within a review case."""

    field_item_id: str
    id: str
    field_path: str
    status: str
    reason_code: str
    display_label: Optional[str] = None
    label: Optional[str] = None
    is_critical: bool = False
    field_confidence: Optional[float] = None
    original_value: Any = None
    proposed_value: Any = None
    final_value: Any = None
    evidence_text: Optional[str] = None
    evidence_snippet: Optional[str] = None
    validation_message: Optional[str] = None
    ui_message: Optional[str] = None
    message: Optional[str] = None
    priority_score: int = 0
    recovery_attempt_number: Optional[int] = None


class FieldCorrectionResponse(BaseModel):
    """Audit trail entry for a reviewed field correction."""

    correction_id: str
    field_item_id: str
    field_path: str
    correction_source: str
    old_value: Any = None
    new_value: Any = None
    correction_reason: Optional[str] = None
    corrected_by_user_id: Optional[str] = None
    created_at: datetime


class ReviewCaseListItem(BaseModel):
    """Summary row for a review case listing."""

    review_id: str
    id: str
    job_id: str
    document_id: Optional[str] = None
    filename: Optional[str] = None
    file_name: Optional[str] = None
    document_type: Optional[str] = None
    doc_type: Optional[str] = None
    source_job_status: str
    review_status: str
    status: str
    priority: str
    priority_score: int = 0
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    reason_codes: List[str] = Field(default_factory=list)
    open_field_count: int = 0
    critical_open_field_count: int = 0
    next_recommended_field: Optional[str] = None
    review_summary: Dict[str, Any] = Field(default_factory=dict)
    age_bucket: str = "fresh"


class ReviewCaseListResponse(BaseModel):
    """Paginated review-case listing."""

    total: int
    page: int
    page_size: int
    review_cases: List[ReviewCaseListItem] = Field(default_factory=list)
    reviews: List[ReviewCaseListItem] = Field(default_factory=list)


class ReviewSummaryResponse(BaseModel):
    """Lightweight review summary for list page headers."""

    generated_at: datetime
    cache_ttl_seconds: float
    total_reviews: int = 0
    open_count: int = 0
    in_progress_count: int = 0
    resolved_count: int = 0
    total_open_fields: int = 0


class ReviewCaseDetailResponse(BaseModel):
    """Detailed review case payload."""

    review_id: str
    id: str
    job_id: str
    document_id: Optional[str] = None
    filename: Optional[str] = None
    file_name: Optional[str] = None
    document_type: Optional[str] = None
    doc_type: Optional[str] = None
    source_job_status: str
    review_status: str
    status: str
    priority: str
    priority_score: int = 0
    validation_decision: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    review_summary: Dict[str, Any] = Field(default_factory=dict)
    validation_summary: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    open_field_count: int = 0
    resolved_field_count: int = 0
    critical_open_field_count: int = 0
    next_recommended_field: Optional[str] = None
    artifacts: Dict[str, str] = Field(default_factory=dict)
    fields: List[ReviewFieldItemResponse] = Field(default_factory=list)
    review_fields: List[ReviewFieldItemResponse] = Field(default_factory=list)
    corrections: List[FieldCorrectionResponse] = Field(default_factory=list)


class ReviewFieldDecisionRequest(BaseModel):
    """Reviewer decision for a field item."""

    action: str = Field(..., description="One of: corrected, accept_original, accept_ai_proposal")
    value: Optional[Any] = Field(None, description="Required when action='corrected'")
    correction_reason: Optional[str] = None


class ReviewCaseResolveRequest(BaseModel):
    """Resolve a review case after all fields are addressed."""

    resolution_notes: Optional[str] = None


class RecoveryAttemptResponse(BaseModel):
    """Single logged recovery attempt."""

    attempt_id: str
    job_id: str
    review_case_id: Optional[str] = None
    attempt_number: int
    mode: str
    strategy: str
    status: str
    model_name: Optional[str] = None
    weak_fields: List[str] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    input_summary: Dict[str, Any] = Field(default_factory=dict)
    output_summary: Dict[str, Any] = Field(default_factory=dict)
    improvement_score: Optional[float] = None
    accepted: Optional[bool] = None
    failure_reason: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None


class RecoveryAttemptListResponse(BaseModel):
    """List of recovery attempts for one job."""

    job_id: str
    total: int
    attempts: List[RecoveryAttemptResponse] = Field(default_factory=list)


class DashboardRecentJobResponse(BaseModel):
    """Compact recent-job item for the dashboard."""

    job_id: str
    file_name: Optional[str] = None
    document_type: Optional[str] = None
    doc_type: Optional[str] = None
    status: str
    submitted_at: Optional[datetime] = None


class DashboardReviewSpotlightResponse(BaseModel):
    """Compact review-case item for the dashboard."""

    review_id: str
    id: str
    job_id: str
    file_name: Optional[str] = None
    document_type: Optional[str] = None
    doc_type: Optional[str] = None
    status: str
    open_field_count: int = 0
    created_at: datetime


class DashboardSummaryResponse(BaseModel):
    """Lightweight dashboard summary payload."""

    generated_at: datetime
    cache_ttl_seconds: float
    health_status: str
    total_jobs: int = 0
    jobs_today: int = 0
    completed_today: int = 0
    completed_count: int = 0
    queued_count: int = 0
    processing_count: int = 0
    needs_review_count: int = 0
    low_confidence_count: int = 0
    failed_count: int = 0
    active_count: int = 0
    success_rate: Optional[float] = None
    open_review_cases: int = 0
    total_open_review_fields: int = 0
    common_review_doc_type: Optional[str] = None
    recent_jobs: List[DashboardRecentJobResponse] = Field(default_factory=list)
    review_spotlight: List[DashboardReviewSpotlightResponse] = Field(default_factory=list)
