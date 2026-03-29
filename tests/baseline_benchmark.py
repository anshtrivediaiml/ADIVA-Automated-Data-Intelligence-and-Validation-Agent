"""
Baseline benchmark runner for extraction quality and runtime.

Usage:
  venv\\Scripts\\python tests\\baseline_benchmark.py

Optional:
  - Create tests/baseline_expected_types.json with:
      {"file_name.ext": "expected_doc_type", ...}
    to calculate document-type accuracy.
  - Maintain tests/baseline_sample_manifest.json for tags and notes.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Any

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from extractor import DocumentExtractor  # noqa: E402

INPUT_DIRS = [ROOT_DIR / "data" / "test_documents", ROOT_DIR / "test_images"]
OUT_DIR = ROOT_DIR / "outputs" / "metrics"
OUT_FILE = OUT_DIR / "baseline_metrics.md"
DETAILED_OUT_FILE = OUT_DIR / "baseline_metrics_detailed.json"
EXPECTED_TYPES_FILE = Path(__file__).parent / "baseline_expected_types.json"
MANIFEST_FILE = Path(__file__).parent / "baseline_sample_manifest.json"
SUPPORTED = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
TERMINAL_STATUSES = ("success", "needs_review", "low_confidence", "error")


def _collect_files() -> List[Path]:
    files: List[Path] = []
    for directory in INPUT_DIRS:
        if not directory.exists():
            continue
        for p in sorted(directory.rglob("*")):
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                files.append(p)
    return files


def _load_expected_types() -> Dict[str, str]:
    if not EXPECTED_TYPES_FILE.exists():
        return {}
    with open(EXPECTED_TYPES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): str(v) for k, v in data.items()}


def _load_manifest() -> Dict[str, Dict[str, Any]]:
    if not MANIFEST_FILE.exists():
        return {}
    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        str(filename): value
        for filename, value in data.items()
        if isinstance(value, dict)
    }


def _safe_mean(values: List[float]) -> float:
    return round(statistics.mean(values), 4) if values else 0.0


def _safe_percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 4)
    values = sorted(values)
    index = (len(values) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    if lower == upper:
        return round(values[lower], 4)
    fraction = index - lower
    interpolated = values[lower] + (values[upper] - values[lower]) * fraction
    return round(interpolated, 4)


def _status_label(status: str) -> str:
    return {
        "success": "OK",
        "needs_review": "REVIEW",
        "low_confidence": "LOW",
        "error": "ERR",
    }.get(status, status.upper())


def main() -> int:
    files = _collect_files()
    if not files:
        print("No benchmark files found in data/test_documents or test_images.")
        return 1

    expected_types = _load_expected_types()
    manifest = _load_manifest()
    extractor = DocumentExtractor()

    rows: List[Dict[str, Any]] = []
    stage_totals: Dict[str, List[float]] = {}
    total_start = time.perf_counter()

    for p in files:
        started = time.perf_counter()
        try:
            result = extractor.extract(str(p))
            elapsed = time.perf_counter() - started
            metadata = result.get("metadata", {})
            classification = result.get("classification", {})
            review = result.get("review", {})
            stage_timings = metadata.get("stage_timings_seconds", {})

            for stage_name, seconds in stage_timings.items():
                stage_totals.setdefault(stage_name, []).append(float(seconds))

            status = str(result.get("status", "unknown"))
            actual_type = classification.get("document_type", "unknown")
            expected_type = expected_types.get(p.name)
            type_match = expected_type is not None and expected_type == actual_type
            manifest_entry = manifest.get(p.name, {})
            tags = manifest_entry.get("tags", [])
            review_reasons = review.get("reasons", []) if isinstance(review, dict) else []
            review_summary = metadata.get("review_summary", {}) if isinstance(metadata, dict) else {}
            ocr_summary = metadata.get("ocr_run_summary", {}) if isinstance(metadata, dict) else {}
            ocr_engine = metadata.get("ocr_engine") or "unknown"
            quality_score = None
            quality_assessment = metadata.get("quality_assessment", {})
            if isinstance(quality_assessment, dict):
                quality_score = quality_assessment.get("overall_score")

            rows.append(
                {
                    "file": p.name,
                    "status": status,
                    "time_s": round(elapsed, 3),
                    "actual_type": actual_type,
                    "expected_type": expected_type or "",
                    "type_match": type_match,
                    "ocr_engine": ocr_engine,
                    "ocr_confidence": ocr_summary.get("average_page_confidence"),
                    "review_reasons": review_reasons,
                    "review_summary": review_summary,
                    "tags": tags,
                    "quality_score": quality_score,
                    "error": "",
                }
            )
            print(f"{_status_label(status):<6} {p.name}  {elapsed:.2f}s  type={actual_type}  engine={ocr_engine}")
        except Exception as exc:
            elapsed = time.perf_counter() - started
            rows.append(
                {
                    "file": p.name,
                    "status": "error",
                    "time_s": round(elapsed, 3),
                    "actual_type": "",
                    "expected_type": expected_types.get(p.name, ""),
                    "type_match": False,
                    "ocr_engine": "",
                    "ocr_confidence": None,
                    "review_reasons": [],
                    "review_summary": {},
                    "tags": manifest.get(p.name, {}).get("tags", []),
                    "quality_score": None,
                    "error": str(exc),
                }
            )
            print(f"ERR {p.name}  {elapsed:.2f}s  {exc}")

    total_elapsed = time.perf_counter() - total_start
    status_counts = Counter(row["status"] for row in rows)
    success_rows = [r for r in rows if r["status"] == "success"]
    weak_rows = [r for r in rows if r["status"] in {"needs_review", "low_confidence"}]
    err_rows = [r for r in rows if r["status"] == "error"]
    times = [float(r["time_s"]) for r in rows]
    engine_counts = Counter(row["ocr_engine"] for row in rows if row["ocr_engine"])

    labeled = [r for r in rows if r["expected_type"]]
    labeled_correct = [r for r in labeled if r["type_match"]]
    doc_type_acc = (len(labeled_correct) / len(labeled) * 100.0) if labeled else None

    stage_avg = {k: _safe_mean(v) for k, v in sorted(stage_totals.items())}
    detailed_payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files_processed": len(rows),
        "status_counts": dict(status_counts),
        "total_runtime_seconds": round(total_elapsed, 3),
        "average_runtime_seconds": _safe_mean(times),
        "p50_runtime_seconds": _safe_percentile(times, 0.50),
        "p95_runtime_seconds": _safe_percentile(times, 0.95),
        "doc_type_accuracy_percent": round(doc_type_acc, 2) if doc_type_acc is not None else None,
        "ocr_engine_counts": dict(engine_counts),
        "stage_timing_averages_seconds": stage_avg,
        "rows": rows,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Baseline Metrics\n\n")
        f.write(f"- Generated at: {generated_at}\n")
        f.write(f"- Files processed: {len(rows)}\n")
        for status in TERMINAL_STATUSES:
            if status in status_counts:
                f.write(f"- {status}: {status_counts[status]}\n")
        f.write(f"- Total runtime (script): {total_elapsed:.2f}s\n")
        f.write(f"- Avg file runtime: {_safe_mean(times):.3f}s\n")
        f.write(f"- P50 file runtime: {_safe_percentile(times, 0.50):.3f}s\n")
        f.write(f"- P95 file runtime: {_safe_percentile(times, 0.95):.3f}s\n")
        if doc_type_acc is None:
            f.write("- Doc-type accuracy: N/A (no labels; add tests/baseline_expected_types.json)\n")
        else:
            f.write(f"- Doc-type accuracy: {doc_type_acc:.2f}% ({len(labeled_correct)}/{len(labeled)})\n")

        f.write("\n## OCR Engine Totals\n\n")
        if engine_counts:
            for engine, count in sorted(engine_counts.items()):
                f.write(f"- {engine}: {count}\n")
        else:
            f.write("- No OCR engine data captured.\n")

        f.write("\n## Stage Timing Averages (seconds)\n\n")
        if stage_avg:
            for stage, value in stage_avg.items():
                f.write(f"- {stage}: {value:.4f}\n")
        else:
            f.write("- No stage timings captured.\n")

        f.write("\n## Review-Required Files\n\n")
        if weak_rows:
            for row in weak_rows:
                reasons = ", ".join(row["review_reasons"]) if row["review_reasons"] else "none_recorded"
                f.write(
                    f"- `{row['file']}`: status={row['status']}, type={row['actual_type']}, "
                    f"engine={row['ocr_engine']}, reasons={reasons}\n"
                )
        else:
            f.write("- No files ended in `needs_review` or `low_confidence`.\n")

        f.write("\n## Per-file Results\n\n")
        f.write("| File | Status | Time (s) | OCR Engine | Actual Type | Expected Type | Type Match |\n")
        f.write("|---|---|---:|---|---|---|---|\n")
        for row in rows:
            f.write(
                f"| {row['file']} | {row['status']} | {row['time_s']:.3f} | "
                f"{row['ocr_engine']} | {row['actual_type']} | {row['expected_type']} | "
                f"{'yes' if row['type_match'] else 'no'} |\n"
            )

        if err_rows:
            f.write("\n## Errors\n\n")
            for row in err_rows:
                f.write(f"- `{row['file']}`: {row['error']}\n")

    with open(DETAILED_OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(detailed_payload, f, indent=2, ensure_ascii=False)

    print(f"\nBaseline report written to: {OUT_FILE}")
    print(f"Detailed report written to: {DETAILED_OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
