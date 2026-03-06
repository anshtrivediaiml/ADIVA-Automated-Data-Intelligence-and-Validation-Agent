"""
Baseline benchmark runner for extraction quality/speed.

Usage:
  venv\\Scripts\\python tests\\baseline_benchmark.py

Optional:
  - Create tests/baseline_expected_types.json with:
      {"file_name.ext": "expected_doc_type", ...}
    to calculate document-type accuracy.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from extractor import DocumentExtractor  # noqa: E402

INPUT_DIRS = [ROOT_DIR / "data" / "test_documents", ROOT_DIR / "test_images"]
OUT_DIR = ROOT_DIR / "outputs" / "metrics"
OUT_FILE = OUT_DIR / "baseline_metrics.md"
EXPECTED_TYPES_FILE = Path(__file__).parent / "baseline_expected_types.json"
SUPPORTED = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


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


def _safe_mean(values: List[float]) -> float:
    return round(statistics.mean(values), 4) if values else 0.0


def main() -> int:
    files = _collect_files()
    if not files:
        print("No benchmark files found in data/test_documents or test_images.")
        return 1

    expected_types = _load_expected_types()
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
            stage_timings = metadata.get("stage_timings_seconds", {})

            for stage_name, seconds in stage_timings.items():
                stage_totals.setdefault(stage_name, []).append(float(seconds))

            actual_type = classification.get("document_type", "unknown")
            expected_type = expected_types.get(p.name)
            type_match = expected_type is not None and expected_type == actual_type

            rows.append(
                {
                    "file": p.name,
                    "status": result.get("status", "unknown"),
                    "time_s": round(elapsed, 3),
                    "actual_type": actual_type,
                    "expected_type": expected_type or "",
                    "type_match": type_match,
                    "error": "",
                }
            )
            print(f"OK  {p.name}  {elapsed:.2f}s")
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
                    "error": str(exc),
                }
            )
            print(f"ERR {p.name}  {elapsed:.2f}s  {exc}")

    total_elapsed = time.perf_counter() - total_start
    ok_rows = [r for r in rows if r["status"] == "success"]
    err_rows = [r for r in rows if r["status"] != "success"]
    times = [float(r["time_s"]) for r in rows]

    labeled = [r for r in rows if r["expected_type"]]
    labeled_correct = [r for r in labeled if r["type_match"]]
    doc_type_acc = (len(labeled_correct) / len(labeled) * 100.0) if labeled else None

    stage_avg = {k: _safe_mean(v) for k, v in sorted(stage_totals.items())}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Baseline Metrics\n\n")
        f.write(f"- Generated at: {generated_at}\n")
        f.write(f"- Files processed: {len(rows)}\n")
        f.write(f"- Success: {len(ok_rows)}\n")
        f.write(f"- Failed: {len(err_rows)}\n")
        f.write(f"- Total runtime (script): {total_elapsed:.2f}s\n")
        f.write(f"- Avg file runtime: {_safe_mean(times):.3f}s\n")
        if doc_type_acc is None:
            f.write("- Doc-type accuracy: N/A (no labels; add tests/baseline_expected_types.json)\n")
        else:
            f.write(f"- Doc-type accuracy: {doc_type_acc:.2f}% ({len(labeled_correct)}/{len(labeled)})\n")

        f.write("\n## Stage Timing Averages (seconds)\n\n")
        if stage_avg:
            for stage, value in stage_avg.items():
                f.write(f"- {stage}: {value:.4f}\n")
        else:
            f.write("- No stage timings captured.\n")

        f.write("\n## Per-file Results\n\n")
        f.write("| File | Status | Time (s) | Actual Type | Expected Type | Type Match |\n")
        f.write("|---|---|---:|---|---|---|\n")
        for row in rows:
            f.write(
                f"| {row['file']} | {row['status']} | {row['time_s']:.3f} | "
                f"{row['actual_type']} | {row['expected_type']} | "
                f"{'yes' if row['type_match'] else 'no'} |\n"
            )

        if err_rows:
            f.write("\n## Errors\n\n")
            for row in err_rows:
                f.write(f"- `{row['file']}`: {row['error']}\n")

    print(f"\nBaseline report written to: {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
