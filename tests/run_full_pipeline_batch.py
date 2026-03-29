"""
Run the full backend pipeline over a directory of documents.

This script uses the real orchestration path:
- create Document / Extraction DB rows
- run extraction
- run validation
- run AI recovery (off/shadow/active)
- inspect final review case fields if still unresolved

Usage:
  .\\venv\\Scripts\\python.exe tests\\run_full_pipeline_batch.py

Examples:
  .\\venv\\Scripts\\python.exe tests\\run_full_pipeline_batch.py --input-dir test_images
  .\\venv\\Scripts\\python.exe tests\\run_full_pipeline_batch.py --recovery-mode shadow
  .\\venv\\Scripts\\python.exe tests\\run_full_pipeline_batch.py --recovery-mode active --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full backend pipeline over a corpus.")
    parser.add_argument("--input-dir", default="test_images", help="Directory containing input files.")
    parser.add_argument("--user-email", default="ansh@adiva.ai", help="User email to associate with created jobs.")
    parser.add_argument(
        "--recovery-mode",
        choices=("off", "shadow", "active"),
        default="active",
        help="How AI recovery should run during the batch.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional limit on number of files to process.")
    parser.add_argument("--output-dir", default="outputs/full_pipeline_runs", help="Directory for summary artifacts.")
    return parser.parse_args()


def configure_runtime(recovery_mode: str) -> None:
    if recovery_mode == "off":
        os.environ["ENABLE_AI_RECOVERY"] = "False"
    elif recovery_mode == "shadow":
        os.environ["ENABLE_AI_RECOVERY"] = "True"
        os.environ["AI_RECOVERY_SHADOW_MODE"] = "True"
    else:
        os.environ["ENABLE_AI_RECOVERY"] = "True"
        os.environ["AI_RECOVERY_SHADOW_MODE"] = "False"


def load_backend_modules(root_dir: Path):
    sys.path.insert(0, str(root_dir / "backend"))

    from db.session import SessionLocal
    from db import models
    from orchestration.service import run_extraction_job
    from review.service import get_open_review_case_id, get_review_case_detail

    return SessionLocal, models, run_extraction_job, get_open_review_case_id, get_review_case_detail


def collect_files(input_dir: Path, limit: int) -> list[Path]:
    files = [
        path
        for path in sorted(input_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if limit > 0:
        return files[:limit]
    return files


def load_output_payload(db, models, extraction_id) -> dict[str, Any]:
    output = (
        db.query(models.ExtractionOutput)
        .filter(models.ExtractionOutput.extraction_id == extraction_id)
        .filter(models.ExtractionOutput.format == "json")
        .first()
    )
    if not output or not output.storage_uri:
        return {}

    output_path = Path(output.storage_uri)
    if not output_path.exists():
        return {}

    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_row(
    *,
    db,
    models,
    extraction,
    extraction_result,
    review_case_id: str | None,
    review_detail,
    output_payload: dict[str, Any],
) -> dict[str, Any]:
    db_metadata = extraction_result.metadata_jsonb if extraction_result and isinstance(extraction_result.metadata_jsonb, dict) else {}
    file_metadata = output_payload.get("metadata", {}) if isinstance(output_payload, dict) else {}
    metadata = {**file_metadata, **db_metadata}
    classification = output_payload.get("classification", {}) if isinstance(output_payload, dict) else {}
    review_payload = output_payload.get("review", {}) if isinstance(output_payload, dict) else {}
    confidence = extraction_result.confidence_jsonb if extraction_result and isinstance(extraction_result.confidence_jsonb, dict) else {}
    if not confidence and isinstance(output_payload, dict):
        confidence = output_payload.get("comprehensive_confidence", {}) or {}
    extraction_confidence = output_payload.get("extraction_confidence")
    recovery_summary = metadata.get("recovery_summary", {}) if isinstance(metadata, dict) else {}
    ocr_run_summary = metadata.get("ocr_run_summary", {}) if isinstance(metadata, dict) else {}
    structured_data = extraction_result.structured_data_jsonb if extraction_result and isinstance(extraction_result.structured_data_jsonb, dict) else {}
    if not structured_data and isinstance(output_payload, dict):
        structured_data = output_payload.get("structured_data") or {}

    attempts = (
        db.query(models.RecoveryAttempt)
        .filter(models.RecoveryAttempt.extraction_id == extraction.id)
        .order_by(models.RecoveryAttempt.attempt_number.asc())
        .all()
    )
    unresolved_fields = []
    if review_detail is not None:
        unresolved_fields = [
            {
                "field_path": field.field_path,
                "reason_code": field.reason_code,
                "validation_message": field.validation_message,
                "proposed_value": field.proposed_value,
                "original_value": field.original_value,
            }
            for field in review_detail.fields
            if field.status == "open"
        ]

    return {
        "file": Path(metadata.get("filename") or "").name or None,
        "job_id": str(extraction.id),
        "status": extraction.status,
        "validation_decision": extraction.validation_decision,
        "review_required": bool(extraction.review_required),
        "review_case_id": review_case_id,
        "review_status": review_detail.review_status if review_detail else None,
        "doc_type": extraction_result.document_type if extraction_result else classification.get("document_type"),
        "dt_conf": classification.get("confidence"),
        "dt_source": classification.get("classification_source"),
        "dt_status": classification.get("classification_status"),
        "lang": metadata.get("detected_language"),
        "lang_code": metadata.get("detected_language_code"),
        "extractor": metadata.get("extractor_used"),
        "quality_score": (metadata.get("quality_assessment") or {}).get("overall_score"),
        "quality_issues": (metadata.get("quality_assessment") or {}).get("issues", []),
        "ocr_conf": ocr_run_summary.get("average_page_confidence"),
        "engine_usage": ocr_run_summary.get("engine_usage", {}),
        "words": len(str((output_payload.get("text") or {}).get("raw") or "").split()),
        "chars": len(str((output_payload.get("text") or {}).get("raw") or "")),
        "has_struct": bool(structured_data),
        "struct_keys": list(structured_data.keys()) if isinstance(structured_data, dict) else [],
        "ext_conf": extraction_confidence,
        "overall_conf": confidence.get("overall_confidence"),
        "grade": confidence.get("confidence_grade"),
        "review_reasons": review_payload.get("reasons", []),
        "validation_summary": metadata.get("validation_summary"),
        "recovery_summary": recovery_summary,
        "recovery_attempts": [
            {
                "attempt_number": attempt.attempt_number,
                "mode": attempt.mode,
                "strategy": attempt.strategy,
                "status": attempt.status,
                "accepted": attempt.accepted,
                "failure_reason": attempt.failure_reason,
                "weak_fields": list(attempt.weak_fields_jsonb or []),
            }
            for attempt in attempts
        ],
        "unresolved_review_fields": unresolved_fields,
        "artifacts": review_detail.artifacts if review_detail else {},
        "processing_time_seconds": metadata.get("processing_time_seconds"),
        "stage_timings_seconds": metadata.get("stage_timings_seconds", {}),
    }


def write_outputs(output_dir: Path, run_id: str, summary: dict[str, Any]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"full_pipeline_{run_id}.json"
    md_path = output_dir / f"full_pipeline_{run_id}.md"

    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Full Pipeline Batch Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Recovery mode: {summary['recovery_mode']}",
        f"- Files processed: {summary['file_count']}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(summary["status_counts"].items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Review Cases Still Open", ""])
    open_review_rows = [row for row in summary["rows"] if row["unresolved_review_fields"]]
    if open_review_rows:
        for row in open_review_rows:
            lines.append(f"- `{row['file']}` -> `{row['status']}` / `{row['doc_type']}`")
            for field in row["unresolved_review_fields"]:
                lines.append(
                    f"  - `{field['field_path']}` [{field['reason_code']}]"
                )
    else:
        lines.append("- No unresolved review fields remained.")

    lines.extend(
        [
            "",
            "## Per-file Summary",
            "",
            "| File | Status | Doc Type | OCR % | Grade | Recovery Attempts | Open Review Fields |",
            "|---|---|---|---:|---|---:|---:|",
        ]
    )
    for row in summary["rows"]:
        ocr_conf = row["ocr_conf"]
        ocr_conf_text = f"{ocr_conf:.1f}" if isinstance(ocr_conf, (int, float)) else ""
        lines.append(
            f"| {row['file']} | {row['status']} | {row['doc_type'] or ''} | "
            f"{ocr_conf_text} | {row['grade'] or ''} | "
            f"{len(row['recovery_attempts'])} | {len(row['unresolved_review_fields'])} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    args = parse_args()
    configure_runtime(args.recovery_mode)

    root_dir = Path(__file__).resolve().parent.parent
    input_dir = (root_dir / args.input_dir).resolve()
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        return 1

    SessionLocal, models, run_extraction_job, get_open_review_case_id, get_review_case_detail = load_backend_modules(root_dir)
    files = collect_files(input_dir, args.limit)
    if not files:
        print(f"No supported files found in: {input_dir}")
        return 1

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    status_counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == args.user_email).first()
        if user is None:
            print(f"User not found: {args.user_email}")
            return 1
        user_id = user.id
    finally:
        db.close()

    for index, source_path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {source_path.name}", flush=True)
        file_started = time.perf_counter()

        db = SessionLocal()
        try:
            document = models.Document(
                user_id=user_id,
                filename=f"pipeline_{run_id}_{source_path.name}",
                mime_type=None,
                size_bytes=source_path.stat().st_size,
                checksum=f"pipeline-{run_id}-{source_path.name}",
                storage_uri=str(source_path),
            )
            db.add(document)
            db.flush()

            extraction = models.Extraction(
                document_id=document.id,
                user_id=user_id,
                status="queued",
                model_name="full-pipeline-batch",
            )
            db.add(extraction)
            db.commit()
            extraction_id = extraction.id
        finally:
            db.close()

        run_extraction_job(str(extraction_id))

        db = SessionLocal()
        try:
            extraction = db.query(models.Extraction).filter(models.Extraction.id == extraction_id).first()
            extraction_result = (
                db.query(models.ExtractionResult)
                .filter(models.ExtractionResult.extraction_id == extraction_id)
                .first()
            )
            review_case_id = get_open_review_case_id(db, extraction_id)
            review_detail = None
            if review_case_id:
                review_detail = get_review_case_detail(db, review_id=review_case_id, user_id=user_id)

            output_payload = load_output_payload(db, models, extraction_id)
            if isinstance(output_payload, dict):
                output_payload.setdefault("metadata", {})
                output_payload["metadata"].setdefault("filename", source_path.name)

            row = build_row(
                db=db,
                models=models,
                extraction=extraction,
                extraction_result=extraction_result,
                review_case_id=review_case_id,
                review_detail=review_detail,
                output_payload=output_payload,
            )
            row["file"] = source_path.name
            row["elapsed_seconds"] = round(time.perf_counter() - file_started, 3)
            rows.append(row)
            status_counts[row["status"]] += 1

            summary_line = (
                f"  status={row['status']} doc_type={row['doc_type']} "
                f"recovery_attempts={len(row['recovery_attempts'])} "
                f"open_review_fields={len(row['unresolved_review_fields'])} "
                f"time={row['elapsed_seconds']}s"
            )
            print(summary_line, flush=True)
            if row["unresolved_review_fields"]:
                for field in row["unresolved_review_fields"][:8]:
                    print(
                        f"    - {field['field_path']} [{field['reason_code']}]",
                        flush=True,
                    )
        finally:
            db.close()

    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "recovery_mode": args.recovery_mode,
        "file_count": len(files),
        "status_counts": dict(status_counts),
        "rows": rows,
    }
    json_path, md_path = write_outputs((root_dir / args.output_dir).resolve(), run_id, summary)

    print("")
    print("Run complete")
    print(f"JSON summary: {json_path}")
    print(f"Markdown summary: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
