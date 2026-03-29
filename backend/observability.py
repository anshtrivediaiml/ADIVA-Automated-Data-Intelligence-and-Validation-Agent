"""
Runtime observability and health helpers.

This module keeps lightweight in-process metrics, writes machine-readable
snapshots to disk, and performs readiness checks for production dependencies.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from importlib.util import find_spec
from threading import Lock
from typing import Any
import json
import os
import shutil
import time

from sqlalchemy import text

from db.session import engine
from logger import logger
from workflow_contract import JobState
import config


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshot_path = config.METRICS_DIR / f"runtime_pipeline_metrics_{os.getpid()}.json"
        self._snapshot_write_interval_seconds = max(
            0.0,
            config.METRICS_SNAPSHOT_MIN_INTERVAL_SECONDS,
        )
        self._last_snapshot_write_monotonic = 0.0
        self._request_counts = Counter()
        self._job_counts = Counter()
        self._job_status_counts = Counter()
        self._validation_decision_counts = Counter()
        self._failure_category_counts = Counter()
        self._stage_transition_counts = Counter()
        self._stage_duration_totals = defaultdict(float)
        self._stage_duration_counts = Counter()
        self._stage_duration_max = defaultdict(float)
        self._job_runtime_totals = defaultdict(float)
        self._job_runtime_counts = Counter()
        self._job_runtime_max = defaultdict(float)

    def record_request(self, *, path: str, method: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self._request_counts["total"] += 1
            self._request_counts[f"method:{method.upper()}"] += 1
            self._request_counts[f"status:{status_code}"] += 1
            self._request_counts[f"path:{path}"] += 1
            self._stage_duration_totals["http_request_ms"] += float(duration_ms)
            self._stage_duration_counts["http_request_ms"] += 1
            self._stage_duration_max["http_request_ms"] = max(
                self._stage_duration_max["http_request_ms"],
                float(duration_ms),
            )
        self._save_snapshot()

    def record_job_submission(self, *, batch: bool = False) -> None:
        with self._lock:
            self._job_counts["submitted"] += 1
            if batch:
                self._job_counts["submitted_batch_item"] += 1
        self._save_snapshot()

    def record_stage_transition(self, *, status: str, current_stage: str) -> None:
        with self._lock:
            self._stage_transition_counts[f"{status}:{current_stage}"] += 1
        self._save_snapshot()

    def record_job_completion(
        self,
        *,
        status: str,
        validation_decision: str | None = None,
        stage_timings: dict[str, Any] | None = None,
        processing_time_seconds: float | None = None,
    ) -> None:
        with self._lock:
            self._job_counts["completed_total"] += 1
            self._job_status_counts[status] += 1
            if validation_decision:
                self._validation_decision_counts[validation_decision] += 1

            if stage_timings:
                for stage_name, raw_value in stage_timings.items():
                    if not isinstance(raw_value, (int, float)):
                        continue
                    value = float(raw_value)
                    self._stage_duration_totals[stage_name] += value
                    self._stage_duration_counts[stage_name] += 1
                    self._stage_duration_max[stage_name] = max(
                        self._stage_duration_max[stage_name],
                        value,
                    )

            if isinstance(processing_time_seconds, (int, float)):
                runtime = float(processing_time_seconds)
                self._job_runtime_totals[status] += runtime
                self._job_runtime_counts[status] += 1
                self._job_runtime_max[status] = max(self._job_runtime_max[status], runtime)
        self._save_snapshot(force=True)

    def record_job_failure(self, *, category: str, reason: str | None = None) -> None:
        with self._lock:
            self._job_counts["failed_total"] += 1
            self._job_status_counts[JobState.FAILED.value] += 1
            self._failure_category_counts[category] += 1
        logger.error(f"Observability failure category recorded | category={category} reason={reason}")
        self._save_snapshot(force=True)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            avg_stage_durations = {
                name: round(self._stage_duration_totals[name] / self._stage_duration_counts[name], 4)
                for name in self._stage_duration_counts
                if self._stage_duration_counts[name]
            }
            avg_job_runtimes = {
                name: round(self._job_runtime_totals[name] / self._job_runtime_counts[name], 4)
                for name in self._job_runtime_counts
                if self._job_runtime_counts[name]
            }

            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "requests": dict(self._request_counts),
                "jobs": {
                    "counts": dict(self._job_counts),
                    "status_counts": dict(self._job_status_counts),
                    "validation_decision_counts": dict(self._validation_decision_counts),
                    "failure_category_counts": dict(self._failure_category_counts),
                    "stage_transition_counts": dict(self._stage_transition_counts),
                    "average_stage_timings_seconds": avg_stage_durations,
                    "max_stage_timings_seconds": {
                        key: round(value, 4) for key, value in self._stage_duration_max.items()
                    },
                    "average_processing_time_seconds": avg_job_runtimes,
                    "max_processing_time_seconds": {
                        key: round(value, 4) for key, value in self._job_runtime_max.items()
                    },
                },
            }

    def _save_snapshot(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if (
            not force
            and self._snapshot_write_interval_seconds > 0
            and now - self._last_snapshot_write_monotonic < self._snapshot_write_interval_seconds
        ):
            return

        snapshot = self.snapshot()
        try:
            temp_path = self._snapshot_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, indent=2)
            os.replace(temp_path, self._snapshot_path)
            self._last_snapshot_write_monotonic = now
        except PermissionError:
            # Another process may momentarily hold the temp or target path on Windows.
            # Skip the snapshot write rather than adding request latency.
            return
        except Exception as exc:
            logger.warning(f"Failed to write runtime metrics snapshot: {exc}")


runtime_metrics = RuntimeMetrics()
_readiness_cache_lock = Lock()
_readiness_cache_value: dict[str, Any] | None = None
_readiness_cache_expires_at = 0.0


def check_storage_health() -> dict[str, Any]:
    directories = {
        "outputs": config.OUTPUTS_DIR,
        "uploads": config.UPLOADS_DIR,
        "extracted": config.EXTRACTED_DIR,
        "validated": config.VALIDATED_DIR,
        "metrics": config.METRICS_DIR,
    }
    statuses = {}
    overall_ok = True
    for name, path in directories.items():
        ok = path.exists() and path.is_dir()
        statuses[name] = {
            "status": "ready" if ok else "missing",
            "path": str(path),
        }
        overall_ok = overall_ok and ok
    return {
        "status": "ready" if overall_ok else "not_ready",
        "details": statuses,
    }


def check_database_health() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "not_ready", "reason": str(exc)}


def check_queue_health() -> dict[str, Any]:
    backend = config.JOB_EXECUTION_BACKEND
    if backend == "local":
        return {"status": "ready", "backend": backend}

    if backend == "celery":
        try:
            from redis import Redis
            from orchestration.tasks import celery_app

            client = Redis.from_url(config.CELERY_BROKER_URL)
            client.ping()
            inspector = celery_app.control.inspect(timeout=1.0)
            worker_pings = inspector.ping() or {}
            workers = sorted(worker_pings.keys())
            if not workers:
                return {
                    "status": "not_ready",
                    "backend": backend,
                    "reason": "No active Celery workers responded",
                }
            return {
                "status": "ready",
                "backend": backend,
                "workers": workers,
            }
        except Exception as exc:
            return {
                "status": "not_ready",
                "backend": backend,
                "reason": str(exc),
            }

    return {"status": "not_ready", "backend": backend, "reason": "Unknown job backend"}


def check_ocr_health() -> dict[str, Any]:
    details = {}
    overall_ok = True

    tesseract_path = config.TESSERACT_CMD_PATH or shutil.which("tesseract")
    if tesseract_path:
        details["tesseract"] = "available"
    else:
        details["tesseract"] = "not_available"
        overall_ok = False

    pytesseract_available = find_spec("pytesseract") is not None
    details["pytesseract"] = "available" if pytesseract_available else "not_available"
    overall_ok = overall_ok and pytesseract_available

    paddleocr_available = find_spec("paddleocr") is not None
    details["paddleocr"] = "available" if paddleocr_available else "not_available"

    easyocr_available = find_spec("easyocr") is not None
    details["easyocr"] = "available" if easyocr_available else "not_available"

    img2table_available = find_spec("img2table") is not None
    details["img2table"] = "available" if img2table_available else "not_available"

    return {
        "status": "ready" if overall_ok else "degraded",
        "details": details,
    }


def check_llm_health() -> dict[str, Any]:
    if not config.MISTRAL_API_KEY:
        return {"status": "not_configured"}
    return {
        "status": "configured",
        "model": config.MISTRAL_MODEL,
        "timeout_ms": config.MISTRAL_TIMEOUT_MS,
    }


@lru_cache(maxsize=1)
def _cached_ocr_health() -> dict[str, Any]:
    return check_ocr_health()


def get_readiness_snapshot() -> dict[str, Any]:
    global _readiness_cache_value
    global _readiness_cache_expires_at

    now = time.monotonic()
    with _readiness_cache_lock:
        if _readiness_cache_value is not None and now < _readiness_cache_expires_at:
            return _readiness_cache_value

    checks = {
        "database": check_database_health(),
        "queue": check_queue_health(),
        "storage": check_storage_health(),
        "ocr": _cached_ocr_health(),
        "llm": check_llm_health(),
    }

    hard_dependencies_ready = (
        checks["database"]["status"] == "ready"
        and checks["queue"]["status"] == "ready"
        and checks["storage"]["status"] == "ready"
        and checks["ocr"]["status"] in {"ready", "degraded"}
    )

    overall_status = "ready" if hard_dependencies_ready else "not_ready"
    snapshot = {
        "status": overall_status,
        "checks": checks,
        "runtime_metrics": runtime_metrics.snapshot(),
    }
    with _readiness_cache_lock:
        _readiness_cache_value = snapshot
        _readiness_cache_expires_at = now + max(0.0, config.READINESS_CACHE_TTL_SECONDS)
    return snapshot
