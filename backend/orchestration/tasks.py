"""
Optional Celery task entrypoints for production queue execution.

The API falls back to local background execution when Celery is unavailable.
"""

from __future__ import annotations

import os
import sys

# Ensure both the project root and backend/ are importable regardless of where
# the Celery worker process is launched from.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_project_root = os.path.dirname(_backend_dir)
for _path in (_project_root, _backend_dir):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import config

try:
    from celery import Celery
except Exception as exc:  # pragma: no cover - optional dependency path
    raise RuntimeError(f"Celery is not installed: {exc}") from exc

from orchestration.service import run_extraction_job


celery_app = Celery(
    "adiva",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
)


@celery_app.task(name="adiva.process_extraction_job")
def process_extraction_job_task(extraction_id: str) -> None:
    run_extraction_job(extraction_id)
