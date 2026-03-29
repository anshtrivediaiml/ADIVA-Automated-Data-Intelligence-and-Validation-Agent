"""
Canonical workflow contract for orchestrated document processing.

Phase 1 defines these values so future queue/worker code can share one source
of truth for job states, terminal outcomes, and validation routing.
"""

from __future__ import annotations

from enum import Enum


class JobState(str, Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    OCR_RUNNING = "ocr_running"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    LOW_CONFIDENCE = "low_confidence"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationDecision(str, Enum):
    PASS = "pass"
    NEEDS_REVIEW = "needs_review"
    LOW_CONFIDENCE = "low_confidence"
    RETRY = "retry"
    FAIL = "fail"


ACTIVE_JOB_STATES = {
    JobState.PREPROCESSING,
    JobState.OCR_RUNNING,
    JobState.CLASSIFYING,
    JobState.EXTRACTING,
    JobState.VALIDATING,
    JobState.EXPORTING,
}


TERMINAL_JOB_STATES = {
    JobState.COMPLETED,
    JobState.NEEDS_REVIEW,
    JobState.LOW_CONFIDENCE,
    JobState.FAILED,
    JobState.CANCELLED,
}


REVIEW_REQUIRED_STATES = {
    JobState.NEEDS_REVIEW,
    JobState.LOW_CONFIDENCE,
}


def is_terminal_job_state(state: str) -> bool:
    return state in {item.value for item in TERMINAL_JOB_STATES}


def requires_review(state: str) -> bool:
    return state in {item.value for item in REVIEW_REQUIRED_STATES}
