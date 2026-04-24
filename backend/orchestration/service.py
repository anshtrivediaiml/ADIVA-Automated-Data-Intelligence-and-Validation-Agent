"""
Async job orchestration helpers.

Phase 2 reuses the Extraction record as the initial job record and moves the
heavy extraction work into a background execution path.
"""

from __future__ import annotations

import os
import sys

# Guarantee both the project root and backend/ are importable when this module
# is loaded by a Celery worker. Worker launch CWD is not stable.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_project_root = os.path.dirname(_backend_dir)
for _path in (_project_root, _backend_dir):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from datetime import datetime, timezone
from pathlib import Path
import threading
from typing import Optional
from uuid import UUID

from api.models.responses import JobSubmissionResponse
from db import models
from db.session import SessionLocal
from logger import logger
from observability import runtime_metrics
from recovery.service import attach_recovery_proposals_if_present, run_bounded_recovery
from review.service import create_or_update_review_case
from workflow_contract import JobState, requires_review
from validation_service import (
    ValidationDecision,
    decide_validation_outcome,
    persist_validation_report,
    promote_final_job_status,
    summarize_validation_report,
    validate_extraction_payload,
)
import config

_extractor = None


def get_extractor():
    global _extractor
    if _extractor is None:
        try:
            from extractor import DocumentExtractor
        except ModuleNotFoundError as exc:
            if exc.name != "extractor":
                raise
            from backend.extractor import DocumentExtractor
        _extractor = DocumentExtractor()
    return _extractor


def build_job_submission_response(
    extraction: models.Extraction,
    document: models.Document,
) -> JobSubmissionResponse:
    submitted_at = extraction.submitted_at or extraction.created_at or datetime.now(timezone.utc)
    extraction_id = str(extraction.id)
    return JobSubmissionResponse(
        job_id=extraction_id,
        document_id=str(document.id),
        status=extraction.status,
        submitted_at=submitted_at,
        status_url=f"/api/jobs/{extraction_id}",
        result_url=f"/api/results/{extraction_id}",
    )


def enqueue_extraction_job(background_tasks, extraction_id: UUID, *, batch: bool = False) -> None:
    runtime_metrics.record_job_submission(batch=batch)
    backend = config.JOB_EXECUTION_BACKEND
    if backend == "celery" and _enqueue_with_celery(str(extraction_id)):
        return
    if backend == "celery":
        logger.warning(
            "JOB_EXECUTION_BACKEND=celery but Celery is unavailable or queueing failed; "
            "falling back to local background execution."
        )
    threading.Thread(
        target=run_extraction_job,
        args=(str(extraction_id),),
        name=f"adiva-job-{str(extraction_id)[:8]}",
        daemon=True,
    ).start()


def _enqueue_with_celery(extraction_id: str) -> bool:
    try:
        from orchestration.tasks import process_extraction_job_task
    except Exception as exc:
        logger.warning(f"Celery task import failed: {exc}")
        return False

    try:
        process_extraction_job_task.delay(extraction_id)
        return True
    except Exception as exc:
        logger.error(f"Celery queue submission failed for job_id={extraction_id}: {exc}")
        return False


def run_extraction_job(extraction_id: str) -> None:
    db = SessionLocal()
    try:
        extraction = (
            db.query(models.Extraction)
            .filter(models.Extraction.id == extraction_id)
            .first()
        )
        if not extraction:
            logger.error(f"Extraction job not found: {extraction_id}")
            return

        document = (
            db.query(models.Document)
            .filter(models.Document.id == extraction.document_id)
            .first()
        )
        if not document or not document.storage_uri:
            extraction.status = JobState.FAILED.value
            extraction.current_stage = None
            extraction.started_at = extraction.started_at or datetime.now(timezone.utc)
            extraction.finished_at = datetime.now(timezone.utc)
            extraction.error_message = "Stored document path is missing"
            db.commit()
            logger.error(f"Extraction job {extraction_id} failed: missing storage_uri")
            return

        extraction.started_at = extraction.started_at or datetime.now(timezone.utc)
        extraction.status = JobState.PREPROCESSING.value
        extraction.current_stage = "quality_assessment"
        extraction.error_message = None
        # Capture values needed after session close BEFORE closing
        storage_uri = document.storage_uri
        db.commit()
        db.close()

        file_path = Path(storage_uri)
        if not file_path.exists():
            extraction.status = JobState.FAILED.value
            extraction.current_stage = None
            extraction.started_at = extraction.started_at or datetime.now(timezone.utc)
            extraction.finished_at = datetime.now(timezone.utc)
            extraction.error_message = f"Stored document not found: {file_path}"
            db = SessionLocal()
            try:
                persisted = (
                    db.query(models.Extraction)
                    .filter(models.Extraction.id == extraction_id)
                    .first()
                )
                if persisted:
                    persisted.status = JobState.FAILED.value
                    persisted.current_stage = None
                    persisted.started_at = persisted.started_at or datetime.now(timezone.utc)
                    persisted.finished_at = datetime.now(timezone.utc)
                    persisted.error_message = f"Stored document not found: {file_path}"
                    db.commit()
            finally:
                db.close()
            logger.error(f"Extraction job {extraction_id} failed: file missing at {file_path}")
            return

        try:
            result = get_extractor().extract(
                str(file_path),
                stage_callback=lambda state, stage_name: _update_job_stage(
                    extraction_id,
                    status=state,
                    current_stage=stage_name,
                ),
            )
        except Exception as exc:
            runtime_metrics.record_job_failure(category="extraction", reason=str(exc))
            raise

        validation_report = None
        validation_decision = None

        if result.get("status") != "error":
            _update_job_stage(
                extraction_id,
                status=JobState.VALIDATING.value,
                current_stage="audit_validation",
            )
            document_type = result.get("classification", {}).get("document_type")
            source_file = result.get("output_file") or str(file_path)
            try:
                validation_report = validate_extraction_payload(
                    result.get("structured_data") or {},
                    source_file=source_file,
                    document_type=document_type,
                )
                validation_decision = decide_validation_outcome(validation_report)
            except Exception as exc:
                runtime_metrics.record_job_failure(category="validation", reason=str(exc))
                raise
        else:
            runtime_metrics.record_job_failure(
                category="extraction_result_error",
                reason=result.get("error"),
            )

        _persist_job_result(
            extraction_id,
            result,
            validation_report=validation_report,
            validation_decision=validation_decision,
        )

    except Exception as exc:
        logger.exception(f"Unexpected extraction job failure for job_id={extraction_id}: {exc}")
        _mark_job_failed(extraction_id, str(exc))
    finally:
        try:
            db.close()
        except Exception:
            pass


def _update_job_stage(extraction_id: str, *, status: str, current_stage: str) -> None:
    db = SessionLocal()
    try:
        extraction = (
            db.query(models.Extraction)
            .filter(models.Extraction.id == extraction_id)
            .first()
        )
        if not extraction:
            return
        extraction.status = status
        extraction.current_stage = current_stage
        extraction.started_at = extraction.started_at or datetime.now(timezone.utc)
        db.commit()
        runtime_metrics.record_stage_transition(status=status, current_stage=current_stage)
        logger.info(
            f"Job stage transition | job_id={extraction_id} status={status} stage={current_stage}"
        )
    except Exception as exc:
        db.rollback()
        logger.warning(
            f"Failed to update stage for job_id={extraction_id}, "
            f"status={status}, stage={current_stage}: {exc}"
        )
    finally:
        db.close()


def _persist_job_result(
    extraction_id: str,
    result: dict,
    *,
    validation_report=None,
    validation_decision: Optional[ValidationDecision] = None,
) -> None:
    db = SessionLocal()
    try:
        extraction = (
            db.query(models.Extraction)
            .filter(models.Extraction.id == extraction_id)
            .first()
        )
        if not extraction:
            logger.error(f"Cannot persist result for missing job_id={extraction_id}")
            return

        extraction_status = _map_pipeline_status_to_job_status(result.get("status", "error"))
        final_status = extraction_status
        validation_summary = None
        if validation_report and validation_decision:
            final_status = promote_final_job_status(extraction_status, validation_decision)
            validation_summary = summarize_validation_report(validation_report, validation_decision)

        recovery_summary = None
        # ── High-confidence bypass gate ─────────────────────────────────────
        # If extraction confidence already 0.90+ (grade A), recovery is very
        # unlikely to improve things and wastes API quota that then rate-limits
        # validation triage. Skip recovery and let the reviewers handle it.
        _extraction_conf = (
            (result.get("comprehensive_confidence") or {})
            .get("overall_score")
            or (result.get("confidence") or {})
            .get("overall", 0.0)
        )
        _high_confidence_extraction = float(_extraction_conf or 0) >= 0.90
        if (
            config.ENABLE_AI_RECOVERY
            and validation_report is not None
            and validation_decision is not None
            and requires_review(final_status)
            and not _high_confidence_extraction
        ):
            recovery_summary = run_bounded_recovery(
                db,
                extraction=extraction,
                result=result,
                validation_report=validation_report,
                validation_decision=validation_decision,
                validation_summary=validation_summary or {},
            )
            if recovery_summary.get("accepted") and recovery_summary.get("activated"):
                result = recovery_summary["accepted_result"]
                validation_report = recovery_summary["accepted_validation_report"]
                validation_decision = recovery_summary["accepted_validation_decision"]
                extraction_status = _map_pipeline_status_to_job_status(result.get("status", "error"))
                final_status = promote_final_job_status(extraction_status, validation_decision)
                validation_summary = summarize_validation_report(validation_report, validation_decision)

        extraction.status = final_status
        extraction.current_stage = None
        extraction.finished_at = datetime.now(timezone.utc)
        extraction.review_required = requires_review(final_status)
        extraction.validation_decision = validation_decision.value if validation_decision else None
        extraction.error_message = result.get("error")

        extraction_result = (
            db.query(models.ExtractionResult)
            .filter(models.ExtractionResult.extraction_id == extraction.id)
            .first()
        )
        if extraction_result is None:
            extraction_result = models.ExtractionResult(extraction_id=extraction.id)
            db.add(extraction_result)

        extraction_result.document_type = result.get("classification", {}).get("document_type")
        extraction_result.structured_data_jsonb = result.get("structured_data")
        extraction_result.confidence_jsonb = result.get("comprehensive_confidence")
        extraction_result.detected_language = result.get("metadata", {}).get("detected_language")
        metadata = dict(result.get("metadata") or {})
        if validation_summary:
            metadata["validation_summary"] = validation_summary
        if recovery_summary:
            metadata["recovery_summary"] = {
                key: value
                for key, value in recovery_summary.items()
                if key not in {"accepted_result", "accepted_validation_report", "accepted_validation_decision"}
            }
        extraction_result.metadata_jsonb = metadata

        db.query(models.ExtractionOutput).filter(
            models.ExtractionOutput.extraction_id == extraction.id
        ).delete()

        output_file = result.get("output_file")
        if output_file:
            db.add(
                models.ExtractionOutput(
                    extraction_id=extraction.id,
                    format="json",
                    storage_uri=output_file,
                    size_bytes=_safe_file_size(output_file),
                )
            )

        for fmt, path in (result.get("exports") or {}).items():
            stored_format = "xlsx" if fmt == "excel" else fmt
            db.add(
                models.ExtractionOutput(
                    extraction_id=extraction.id,
                    format=stored_format,
                    storage_uri=path,
                    size_bytes=_safe_file_size(path),
                )
            )

        if validation_report and validation_decision:
            persist_validation_report(
                validation_report,
                user_id=extraction.user_id,
                extraction_id=str(extraction.id),
                decision=validation_decision,
            )

        if extraction.review_required:
            review_validation_errors = []
            if validation_report:
                review_validation_errors = [
                    {
                        "pillar": item.pillar.value if hasattr(item.pillar, "value") else str(item.pillar),
                        "severity": item.severity.value if hasattr(item.severity, "value") else str(item.severity),
                        "field": item.field,
                        "message": item.message,
                        "expected": item.expected,
                        "actual": item.actual,
                    }
                    for item in validation_report.error_log
                ]
            document = None
            if extraction.document_id:
                document = (
                    db.query(models.Document)
                    .filter(models.Document.id == extraction.document_id)
                    .first()
                )
            review_case = create_or_update_review_case(
                db,
                extraction=extraction,
                document=document,
                document_type=extraction_result.document_type,
                structured_data=extraction_result.structured_data_jsonb or {},
                confidence_data=extraction_result.confidence_jsonb or {},
                validation_summary=validation_summary or {},
                validation_errors=review_validation_errors,
                raw_text=str((result.get("text") or {}).get("raw") or ""),
            )
            if review_case:
                metadata["review_case"] = {
                    "id": str(review_case.id),
                    "status": review_case.status,
                }
                attach_recovery_proposals_if_present(
                    db,
                    review_case=review_case,
                    recovery_summary=recovery_summary,
                )
                extraction_result.metadata_jsonb = metadata

        db.add(
            models.AuditLog(
                user_id=extraction.user_id,
                action="extract_async",
                resource_type="extraction",
                resource_id=str(extraction.id),
                metadata_jsonb={
                    "status": final_status,
                    "document_type": extraction_result.document_type,
                    "review_required": extraction.review_required,
                    "validation_decision": extraction.validation_decision,
                },
            )
        )
        db.commit()
        _log_persisted_job_summary(
            extraction=extraction,
            extraction_result=extraction_result,
            validation_summary=validation_summary,
            recovery_summary=recovery_summary,
        )
        runtime_metrics.record_job_completion(
            status=final_status,
            validation_decision=extraction.validation_decision,
            stage_timings=metadata.get("stage_timings_seconds", {}),
            processing_time_seconds=metadata.get("processing_time_seconds"),
        )
        logger.info(f"Extraction job completed: job_id={extraction_id}, status={final_status}")
    except Exception as exc:
        db.rollback()
        logger.exception(f"Failed to persist extraction job result for job_id={extraction_id}: {exc}")
        runtime_metrics.record_job_failure(category="persistence", reason=str(exc))
        _mark_job_failed(extraction_id, f"Result persistence failed: {exc}")
    finally:
        db.close()


def _mark_job_failed(extraction_id: str, reason: str) -> None:
    db = SessionLocal()
    try:
        extraction = (
            db.query(models.Extraction)
            .filter(models.Extraction.id == extraction_id)
            .first()
        )
        if not extraction:
            return
        extraction.status = JobState.FAILED.value
        extraction.current_stage = None
        extraction.finished_at = datetime.now(timezone.utc)
        extraction.error_message = reason
        db.commit()
        runtime_metrics.record_job_failure(category="workflow", reason=reason)
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to mark job as failed for job_id={extraction_id}: {exc}")
    finally:
        db.close()


def _map_pipeline_status_to_job_status(status: str) -> str:
    return {
        "success": JobState.COMPLETED.value,
        "needs_review": JobState.NEEDS_REVIEW.value,
        "low_confidence": JobState.LOW_CONFIDENCE.value,
        "error": JobState.FAILED.value,
    }.get(status, JobState.FAILED.value)


def _safe_file_size(path: str) -> Optional[int]:
    target = Path(path)
    if target.exists():
        return target.stat().st_size
    return None


def _log_persisted_job_summary(
    *,
    extraction: models.Extraction,
    extraction_result: models.ExtractionResult,
    validation_summary: Optional[dict],
    recovery_summary: Optional[dict],
) -> None:
    logger.info(
        f"Persisted job result | job_id={extraction.id} status={extraction.status} "
        f"doc_type={extraction_result.document_type or 'unknown'} "
        f"validation={extraction.validation_decision or 'n/a'} "
        f"review_required={bool(extraction.review_required)} "
        f"truth_failures={(validation_summary or {}).get('failed_truth_tests', 0)} "
        f"recovery_reason={(recovery_summary or {}).get('reason')} "
        f"recovery_attempts={len((recovery_summary or {}).get('attempts') or [])}"
    )
