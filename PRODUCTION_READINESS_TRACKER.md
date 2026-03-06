# Production Readiness Tracker

**Project:** ADIVA  
**Start Date:** 2026-02-25  

## Limitations (Identified)
- Multiple API entry points (`backend/main.py` and `backend/api/main.py`) caused confusion and missing routes when following README.

## Changes Implemented
### 2026-02-25
- Unified runtime entry point to `api.main:app` while keeping `backend/main.py` as a thin launcher.
- Updated README run instructions to use the unified entry point.
- Updated auth middleware to use HTTP Bearer tokens consistently and return a clear `Not authenticated` response when missing.
- Hardened file uploads: safe filename handling, streamed writes, configurable 200MB limit, and magic-byte content validation.
- Added PostgreSQL database schema, SQLAlchemy models, and Alembic migrations for production-grade persistence.
- Persisted extraction runs to DB (`documents`, `extractions`, `extraction_results`, `extraction_outputs`) on both single and batch endpoints.
- Replaced hardcoded auth with DB-backed users and added admin seeding workflow.
- Added admin reset script to delete dummy admin and upsert real admin credentials.
- Linked `documents.user_id` and `extractions.user_id` to the authenticated user.
- Updated results and listing endpoints to read from DB instead of filesystem.
- Switched `extraction_id` to DB UUIDs across responses and results/download/delete endpoints.

### 2026-03-05
- Fixed `POST /api/extract/batch` cleanup bug where tuple entries in `temp_paths` were treated as `Path` objects in `finally`, causing `AttributeError: 'tuple' object has no attribute 'exists'`.
- Batch endpoint now preserves the intended file-validation HTTP error response path (for example invalid PNG now returns a clean 400 instead of cascading to 500).
- Reworked image content validation to use Pillow decode/verify for `.png/.jpg/.jpeg/.tiff/.bmp` uploads instead of brittle header-only checks; this restores acceptance for valid image uploads in real-world batch cases.
- Added extension/content mismatch tolerance for images with a warning log (prevents hard-fail when client-side filename extension is incorrect but file content is valid).
- Added stage-level extraction timings in `backend/extractor.py` (`preprocess`, `extract_text`, `classify`, `structured_extract`, etc.) and included them in response metadata as `stage_timings_seconds` for baseline performance tracking.
- Added `tests/baseline_benchmark.py` to generate a repeatable baseline report at `outputs/metrics/baseline_metrics.md` (speed summary + stage averages + optional doc-type accuracy when labels are provided).
