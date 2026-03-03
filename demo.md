# Database Modifications (Supabase/Postgres)

## Summary
Added a production‑grade PostgreSQL schema and migrations, targeting Supabase‑hosted Postgres. The design is single‑tenant and supports versioned extractions.

## Files Added
- `backend/db/base.py` (SQLAlchemy base)
- `backend/db/session.py` (DB session/engine)
- `backend/db/models.py` (ORM models)
- `backend/db/migrations/env.py` (Alembic env with DATABASE_URL)
- `backend/db/migrations/versions/0001_initial.py` (Initial schema migration)
- `alembic.ini` (Alembic config)

## Files Updated
- `backend/config.py` (added `DATABASE_URL` requirement)
- `.env.example` (added Supabase connection string example and upload settings)
- `requirements.txt` (added `sqlalchemy`, `alembic`, `psycopg[binary]`)
- `README.md` (Supabase setup and migration steps)

## Schema Overview
Tables created by migration:
- `users`
- `documents`
- `extractions` (includes `version`)
- `extraction_results`
- `extraction_outputs`
- `validation_reports`
- `audit_logs`

Indexes:
- `users.email` (unique)
- `documents.checksum`
- `extractions (status, created_at)`
- `extraction_results.document_type`
- GIN index on `extraction_results.structured_data_jsonb`

## Notes
- Connection should use Supabase **pooler** URL (port `6543`) when IPv4 is required.
- `DATABASE_URL` must include `postgresql+psycopg://` and `sslmode=require`.

## Runtime Integration Added
- Extraction endpoints now persist:
  - `documents` (file metadata and checksum)
  - `extractions` (status + model info)
  - `extraction_results` (structured data + confidence + metadata)
  - `extraction_outputs` (paths to exported files)

## DB-Backed Auth
- Hardcoded users removed.
- Auth now verifies against `users` table.
- Admin seeding script: `backend/db/seed_admin.py`.
- Admin reset script: `backend/db/reset_admin.py`.

## User Ownership
- `documents.user_id` and `extractions.user_id` now stored from authenticated user.

## Results From DB
- `/results`, `/download`, `/extractions`, and delete now read from DB instead of filesystem.

## Extraction IDs
- API now returns DB UUIDs as `extraction_id` for all result and download operations.
