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
