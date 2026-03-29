# Production Readiness Tracker

**Project:** ADIVA  
**Start Date:** 2026-02-25  

## Limitations (Identified)
- Multiple API entry points (`backend/main.py` and `backend/api/main.py`) caused confusion and missing routes when following README.

## Active Execution Plan
- The current backend roadmap is defined in `BACKEND_EXECUTION_ROADMAP.md`.
- That roadmap is the planning document for what to build next.
- This tracker remains the implementation log for what has actually been completed, verified, or improved.
- Every completed backend task should be recorded here with:
  - date
  - summary of the change
  - impact on production readiness

## Changes Implemented
### 2026-03-28
- Added frontend job deletion support on the current UI base:
  - wired `DELETE /api/extractions/{job_id}` through `frontend/src/lib/api/jobsApi.ts`
  - added a confirmed delete action to each row in `frontend/src/features/jobs/JobsPage.tsx`
  - added a confirmed `Delete Job` button to `frontend/src/features/jobs/JobDetailPage.tsx`
  - invalidates jobs/reviews/result/recovery queries after deletion and redirects back to `/jobs` from the detail page
- Replaced the browser-native delete confirmation with an in-app confirmation dialog in `frontend/src/components/ui/ConfirmDialog.tsx`, keeping destructive actions visually consistent with the rest of the interface on both the jobs table and job-detail page.
- Verified the frontend delete-flow changes with `npx tsc -b` in `frontend/`
- Impact: users can now remove duplicate, mistaken, or QA-created jobs directly from the UI instead of leaving operational clutter behind.

- Completed the requested backend refinement pass for points 2-5:
  - **Result/review contract polish:** enriched `backend/api/models/responses.py` so result and review payloads now expose stable frontend-friendly aliases (`id`, `label`, `message`), explicit `review_status`, critical-open counts, review summaries, and a `reviews` alias alongside `review_cases` for list responses.
  - **Review payload quality:** updated `backend/review/service.py` to build cleaner review summaries, attach richer field metadata to both result and review responses, and suppress self-contradictory validator text such as "no issue here" / "initial concern was misplaced" before it reaches the UI.
  - **Weak document-type cleanup:** extended deterministic post-processing in `backend/ai_agent.py` beyond payslips and balance sheets to cover `bank_statement`, `marksheet`, and `utility_bill`, including transaction/subject-row deduplication, numeric coercion, and whitespace normalization before any repair logic runs.
  - **Performance refinement:** slimmed the `/api/jobs` list query in `backend/api/routes/jobs.py` so it now loads only the fields needed for the jobs grid instead of pulling full extraction payload JSON, and tightened review-list counting in `backend/review/service.py` so count queries no longer pay for the document join.
  - **Route cleanup:** removed the stray dead block left at the end of `backend/api/routes/results.py` after the earlier QA hotfix and expanded result payloads to include review status/summary metadata directly.
- Verified the touched backend modules with direct `compile(...)` checks and import-level checks using the backend package path for:
  - `backend/api/models/responses.py`
  - `backend/review/service.py`
  - `backend/api/routes/review.py`
  - `backend/api/routes/jobs.py`
  - `backend/api/routes/results.py`
  - `backend/ai_agent.py`
- Impact: backend payloads are now easier for the frontend to consume consistently, noisy review messaging is reduced, weaker document families get safer deterministic cleanup before escalation, and the heaviest list endpoints avoid loading unnecessary JSON blobs.

### 2026-03-16
- **Phases 1–7: Full frontend build completed** following `FRONTEND_IMPLEMENTATION_PLAN.md` exactly.
- Created production-grade `frontend/` app with Vite + React 18 + TypeScript + Tailwind CSS + TanStack Query + React Hook Form + Zod + Axios. `Design app screens/` retained as reference; `frontend/` is the long-term production root.
- **Phase 1 — Foundation:** Vite project scaffold, global CSS with design tokens (#0F0F1A / #4F46E5/ #2A2A3E), all TypeScript types mirroring the backend contract, 5 typed API modules (auth, jobs, results, reviews, health), Axios interceptor with 401→refresh→retry, token store (access in memory, refresh in sessionStorage).
- **Phase 2 — Auth and App Shell:** AuthContext (silent re-auth on mount via refresh token), ProtectedRoute guard (spinner → redirect to /login), AppShell layout (Sidebar + Outlet), Sidebar with real user info and logout button, Login page wired to `POST /api/auth/login` with Zod form validation and server error display.
- **Phase 3 — Dashboard and Jobs:** Dashboard (real `GET /api/jobs` + `GET /api/health`, stat cards, search+filter table, skeleton loading, empty state), JobsPage (full jobs history), JobDetailPage (live polling every 3s until terminal status, stage timeline, per-status CTAs to result/review).
- **Phase 4 — Upload:** SingleUploadPage (drag-drop, file validation, `POST /api/extract`, job redirect), BatchUploadPage (multi-file up to 20, `POST /api/extract/batch`).
- **Phase 5 — Results:** ResultPage with 4 tabs (Structured Data, Validation Report with flagged fields, Recovery Attempts, Downloads), wired to `GET /api/results/{id}` and `GET /api/jobs/{id}/recovery-attempts`. Downloads tab shows available formats from `artifacts` map.
- **Phase 6 — Reviews:** ReviewQueuePage (real `GET /api/reviews`, open field count per case), ReviewCasePage (field-by-field correction editor, AI proposed value acceptance button, `POST /api/reviews/{id}/fields/{fieldId}/correct`, progress bar, `POST /api/reviews/{id}/resolve`, query invalidation on mutations).
- **Phase 7 — System and Hardening:** SystemPage (real `GET /api/health` + `GET /api/status`, glowing status dot by health level, per-service latency rows, raw status JSON viewer, auto-refresh 30s). No mock data anywhere in wired routes.
- **Verified:** `npm install` completed with 248 packages and exit 0. `npm run dev` started Vite at **http://localhost:5173** in 1089ms with no errors.
- **Impact:** Frontend is now a real integrated application, not a design shell. Any developer can `cd frontend && npm install && npm run dev` and connect to the backend.


### 2026-03-15
- Added the final document-specific backend calibration pass before frontend handoff:
  - `purchase_order` and `retail_receipt` now suppress historical-date noise and contextual arithmetic false positives when the extracted commerce math is already internally consistent.
  - `payslip` validation now accepts leap-year dates such as `2024-02-29`, suppresses archived-pay-period noise, and only keeps real arithmetic mismatches.
  - `balance_sheet` validation now ignores subjective `Capital WIP` / “amount seems high” semantic complaints and only keeps actual balancing mismatches.
  - `income_tax_acknowledgment` validation no longer treats `tax_paid > total_tax_payable` as categorically impossible.
  - Added a targeted payslip post-extraction repair pass in `backend/ai_agent.py` that asks the LLM to reconcile earnings, deductions, and net pay only when the initial extracted JSON is internally inconsistent.
  - Added a targeted balance-sheet post-extraction repair pass in `backend/ai_agent.py` that re-groups assets / liabilities only when extracted section totals do not reconcile to the printed totals.
  - Added a low-signal `gst_certificate` downgrade guard in `backend/ai_agent.py` so weak OCR text without real GST markers now falls back to `other` instead of forcing GST schema validation.
- Hardened the validation input path in `backend/orchestration/service.py` so the validator now audits only `structured_data` instead of the full extraction envelope; this prevents metadata, OCR runtime summaries, raw text blobs, and output-file paths from being treated as business fields.
- Tightened contextual-sanity filtering in `backend/agents/validator/logic.py` so optional contact-style fields and non-reviewable internal paths no longer create review pressure, and added a small JSON-repair step for common trailing-comma LLM output before parse fallback.
- Hardened review-case generation in `backend/review/service.py` so internal paths (`metadata.*`, `ocr_run_summary.*`, `review_summary.*`, `text.raw*`) and fake document-level fallback fields are no longer surfaced as review items.
- Switched missing-field escalation in `backend/review/service.py` to be schema-aware by reusing schema `get_required_fields()` plus the existing critical-field map, reducing false `missing_critical_field` review items for optional fields like customer email/phone and similar contact fields.
- Improved `tests/run_full_pipeline_batch.py` so batch summaries read metadata and confidence from the persisted DB result instead of relying only on the original saved `extraction.json`, making future full-pipeline debugging more trustworthy.
- Verified the touched modules with no-write `compile(...)` checks, import-level checks for orchestration/review/validator modules, and targeted logic checks confirming that metadata paths are dropped and optional missing contact fields no longer become review items.
- Refined validator decisioning in `backend/validation_service.py` so unsupported/generic document types now degrade to `low_confidence` instead of being treated like hard semantic failures, and a clean validation `pass` can now promote a previously weak extraction to `completed`.
- Added validation calibration controls in `backend/config.py` and `.env.example` so Pillar 4 truth tests are disabled by default and their confidence weight is configurable instead of dominating review routing.
- Tightened contextual-sanity filtering in `backend/agents/validator/logic.py` for `prescription` and `form_16` so historical dates, prescription shorthand frequencies (`1-0-1`, `0-0-1`), free-form follow-up text, explicit gender values, and archived assessment years no longer create unnecessary review pressure.
- Normalized bracket-style field paths across validator/review/recovery helpers so paths like `medicines[0].frequency` now resolve to the actual extracted value instead of showing `null` in review and recovery payloads.
- Verified these calibration changes with compile checks plus targeted logic checks confirming: unsupported docs now route to `low_confidence`, `PASS` now rescues final status to `completed`, prescription/form-16 false-positive patterns are filtered, and bracket-path lookups now read the correct original values.
- Added a schema-aware Pillar 2 field allowlist in `backend/agents/validator/logic.py` so semantic validation now focuses on high-value business fields per document type instead of optional or stylistic fields.
- Suppressed additional opinion-heavy contextual findings in `backend/agents/validator/logic.py` for prescriptions, marksheets, contracts, and utility bills, reducing review pressure from vague-instruction warnings, subject-name abbreviation complaints, overly strict address expectations, and optional fixed-charge/tax assumptions.
- Added softer severity coercion for contextual issues so only clearly hard contradictions remain `error`; weaker semantic suggestions now degrade to `warning`, which keeps the validator stricter on concrete mistakes and lighter on subjective judgments.
- Verified the latest filtering pass with targeted logic checks showing that noisy messages from the latest 26-file batch are now dropped while concrete mismatches like percentage math errors and missing required provider names still survive validation.
- Added deterministic suppression guards in `backend/agents/validator/logic.py` for clearly valid semantic cases: correct invoice arithmetic can no longer be overruled by Pillar 2, valid cheque amount-words / IFSC / MICR / stale-date cases are no longer mis-flagged, Aadhaar numbers with 12 digits are accepted regardless of spacing, and archived or term-based contract/marksheet complaints are filtered when the underlying values are still coherent.
- Verified the final validation pass with compile checks plus targeted logic tests confirming that: purchase-order and receipt-style invoice math now survives contextual validation when totals are actually correct; cheque false positives for amount words, IFSC, MICR, stale dates, and long account numbers are dropped; valid 12-digit Aadhaar IDs no longer produce review pressure; and schema-renaming contract obligation complaints are filtered.
- Added masked-identifier handling in `backend/agents/validator/logic.py` so partially redacted Aadhaar and bank-account numbers are no longer treated as invalid-format errors when the visible structure is still acceptable for review-safe outputs.
- Suppressed remaining bank-statement stale/gap noise in `backend/agents/validator/logic.py`, specifically old-but-valid statement end dates, inferred “missing transaction gap” complaints, and transaction dates that are actually inside the extracted statement period.
- Verified these last validator fixes with compile checks and targeted logic tests confirming that masked Aadhaar values like `4512 XXXX XXXX 9876` now pass filtering, and the previous bank-statement account-format / stale-date / missing-gap / out-of-period false positives are now dropped.
- Added first-class schema support in `backend/schemas/extended_business_schemas.py` for `purchase_order`, `retail_receipt`, `bill_of_lading`, `lab_report`, `payslip`, `balance_sheet`, and `income_tax_acknowledgment`, with conservative required fields and extraction instructions aligned to the actual sample corpus.
- Registered those new document types in `backend/schemas/__init__.py`, which automatically expands the allowed LLM classification types and enables schema-backed structured extraction for them.
- Added heuristic classifier coverage in `backend/ai_agent.py` for all new document types so the fallback path can now recognize PO, receipt, bill of lading, lab report, payslip, balance sheet, and ITR acknowledgment patterns instead of collapsing them into nearby legacy types.
- Added focused validator support in `backend/agents/validator/logic.py` for the new schemas, including contextual field allowlists and deterministic logical checks for `payslip` totals and `balance_sheet` balancing.
- Verified the schema-expansion pass with compile checks, schema-registry checks, and heuristic-classifier smoke checks confirming that all seven new types are registered and are recognized by the fallback classifier.

### 2026-03-14
- Updated `BACKEND_EXECUTION_ROADMAP.md` to lock the next implementation sequence more clearly: Phase 5 review/correction foundation first, then recovery-attempt logging, then bounded AI recovery inside the current backend, with `LangGraph` explicitly deferred for now.
- Clarified in the roadmap that the post-validation weak-case path should become: deterministic pipeline -> bounded AI field repair -> deterministic re-validation -> human review only for unresolved fields.
- Added roadmap guidance for Phase 5 scope, recovery logging, bounded AI recovery behavior, shadow mode, and the immediate build checklist so future implementation can be judged against one documented plan instead of ad hoc decisions.
- Added `PHASE5_PRE_IMPLEMENTATION_CHECKLIST.md` to lock the pre-build decisions required before Phase 5 starts: first-wave document types, critical fields, review reason codes, acceptance rules, review payload shape, correction-history rules, recovery metrics, bounded-recovery rules, and rollout guardrails.
- Filled `PHASE5_PRE_IMPLEMENTATION_CHECKLIST.md` with conservative V1 decisions aligned to the existing schema and validator behavior: first-wave scope is now locked to `invoice` and `bank_statement`, required critical fields and reason codes are defined, recovery acceptance/review-routing rules are fixed, and the checklist now explicitly protects the already-working happy path from becoming stricter during the first implementation.
- Implemented the Phase 5 backend foundation by adding durable review storage models for `review_cases`, `review_field_items`, and `field_corrections` in `backend/db/models.py` plus Alembic migration `0004_add_review_foundation.py`.
- Added `backend/review/service.py` as the review domain service for building field-level review items from validation issues, creating or updating review cases from weak jobs, applying reviewer field decisions, preserving correction history, and resolving review cases back into the extraction result safely.
- Added review APIs in `backend/api/routes/review.py` and wired them into `backend/api/main.py`, covering review-case listing, review-case detail, field-level review decisions, and case resolution.
- Updated orchestration finalization in `backend/orchestration/service.py` so jobs that already finish as `needs_review` or `low_confidence` now auto-create a review case without changing the current successful extraction path.
- Updated existing job/result surfaces so clients can discover `review_case_id` for weak jobs and updated extraction deletion so review records are cleaned up with the extraction instead of leaking orphaned review data.
- Verified the new Phase 5 foundation with `python -m compileall` for the modified backend modules and import-level checks through the project `venv` confirming that the review service and `/api/reviews` router load successfully.
- Implemented the recovery logging foundation by adding durable `recovery_attempts` storage in `backend/db/models.py` plus Alembic migration `0005_add_recovery_attempts.py`.
- Added `backend/recovery/service.py` with minimal creation/finalization helpers and user-scoped listing/count helpers so later bounded AI recovery can be measured without changing current extraction behavior yet.
- Added `GET /api/jobs/{job_id}/recovery-attempts` and exposed `recovery_attempt_count` in job/result payloads so future recovery runs can be inspected and audited through the existing API surface.
- Updated extraction deletion to remove linked `recovery_attempts` records so the new audit data does not leave orphaned rows behind.
- Verified the recovery logging foundation with `python -m compileall` and a project-venv import check confirming the recovery service loads and the `/api/jobs/{job_id}/recovery-attempts` route is registered.
- Implemented the first bounded AI recovery path in `backend/recovery/service.py`, including eligibility gates, weak-field selection from validation output, one focused LLM repair pass per attempt, deterministic re-validation, explicit acceptance checks, recovery-attempt persistence, and optional proposal attachment back into review cases.
- Extended `backend/ai_agent.py` with a dedicated weak-field repair method so recovery reuses the existing Mistral client instead of introducing a second LLM stack or graph runtime.
- Wired bounded recovery into `backend/orchestration/service.py` so it only runs for jobs that already end as `needs_review` or `low_confidence`, and only changes the persisted result when recovery is enabled and passes the strict acceptance gates.
- Added conservative recovery feature flags in `backend/config.py` and `.env.example`, with `ENABLE_AI_RECOVERY=False` and `AI_RECOVERY_SHADOW_MODE=True` as the safe defaults so the new path does not alter production behavior until explicitly enabled.
- Kept the happy path protected: successful jobs still bypass recovery entirely, and weak jobs still fall back to review if recovery is out of scope, unsupported, or not clearly better.
- Verified the bounded recovery implementation with `python -m compileall` and a project-venv import check confirming the recovery runner loads and the existing recovery-attempt API route remains registered.
- Applied Alembic migrations through `0005_add_recovery_attempts` against the configured database, so the review and recovery tables now exist in the live backend DB.
- Ran real weak-case smoke tests through the orchestration path and confirmed the jobs themselves completed to terminal states instead of hanging; the long-running shell process came from the ad hoc smoke-test harness, not from the extraction workflow itself.
- Confirmed the current environment blockers are operational rather than architectural: Mistral calls are still failing with connection-refused errors, and PaddleOCR fallback can still fail when model hosting is unreachable and local models are not cached.
- Confirmed the latest weak smoke-test jobs finished as `low_confidence` with review required, and recovery attempts were logged safely as skipped rather than silently modifying extraction results.
- Hardened backend startup logging in `backend/config.py` and `backend/logger.py` so per-process log filenames are unique and file-sink failures no longer block the backend from starting; the app now falls back to console logging if file logging cannot be opened.
- Confirmed `backend/db/session.py` is configured with `prepare_threshold=None`, matching the earlier production fix for duplicate prepared statements against the pooled PostgreSQL setup.
- Improved `tests/baseline_benchmark.py` so corpus validation now reports real pipeline terminal states (`success`, `needs_review`, `low_confidence`, `error`) instead of collapsing everything that is not `success` into a generic failure bucket.
- Extended corpus reporting so the benchmark now also writes `outputs/metrics/baseline_metrics_detailed.json` with per-file OCR engine, review reasons, tags, and timing summaries for cleaner audit and comparison.
- Updated `tests/baseline_sample_manifest.json` to include the newly added document images so the next full-corpus run carries useful tags and notes for the new files.
- Added `FRONTEND_START_CHECKLIST.md` to lock the minimum backend expectations, known runtime limitations, and the safe frontend-start assumptions.
- Removed the import-time config crash path by stopping `backend/config.py` from calling `validate_config()` at module import; config validation now happens at API startup instead, so scripts and tests can import backend modules without immediately failing on env checks.
- Hardened OCR portability by replacing the hardcoded Windows Tesseract path with an env-driven `TESSERACT_CMD_PATH` override plus a safe common-Windows-path fallback in `backend/extractors/ocr_extractor.py`, and documented the new env var in `.env.example`.
- Hardened orchestration startup by replacing the eager module-level `DocumentExtractor()` singleton in `backend/orchestration/service.py` with lazy initialization, so the module can import cleanly before OCR/AI components are instantiated.
- Added `GET /api/jobs` in `backend/api/routes/jobs.py` so the frontend now has a basic jobs-history endpoint instead of only single-job lookup.
- Fixed the validator document-type hint keys in `backend/agents/validator/logic.py` so `aadhar_card`, `pan_card`, and `gst_certificate` now match the schema registry naming used elsewhere in the backend.
- Verified these hardening changes with no-write syntax checks plus import-level checks confirming that `config` imports cleanly, `api.main` imports cleanly, `/api/jobs` is registered, `/api/reviews` remains registered, and orchestration no longer instantiates the extractor on import.
- Added `tests/run_full_pipeline_batch.py` as a real backend workflow runner that creates jobs in the DB, executes orchestration, validation, AI recovery (`off` / `shadow` / `active`), and reports unresolved review fields per document at the end of the run.
- Adjusted console logging in `backend/logger.py` so terminal output no longer colorizes the full line by default; color is now controlled by `LOG_COLORIZE`, which defaults to `False`, avoiding misleading red terminal output for non-error lines.
- Verified the new batch runner with no-write syntax checks and a `--help` invocation confirming the CLI loads correctly.
- This documentation update reduces execution ambiguity and prevents Phase 5, Phase 6, and agentic work from being mixed together prematurely.

### 2026-03-13
- Defined the backend workflow contract for the orchestration-first architecture in `PHASE1_BACKEND_CONTRACT.md`, covering canonical job states, state transitions, validation routing, API behavior, durable artifact ownership, retry rules, timeout rules, and batch/review behavior.
- Added a shared `backend/workflow_contract.py` module with canonical job states, validation decisions, and helper predicates so future orchestration code has one source of truth instead of duplicating status strings.
- Added planned async response models in `backend/api/models/responses.py` for job submission, batch submission, job status, and final result payloads so Phase 2 can implement the worker-based API against an already-defined contract.
- This completes the Phase 1 design baseline and removes ambiguity before building the orchestration layer.
- Verified the new Python contract artifacts with `python -m compileall` for `backend/workflow_contract.py` and `backend/api/models/responses.py`.
- Implemented the Phase 2 orchestration foundation by converting `POST /api/extract` and `POST /api/extract/batch` into async job-submission endpoints that return queued job metadata instead of waiting for full extraction results.
- Added durable upload storage under `outputs/uploads` so database records now point to persistent raw documents instead of temp files that disappear at the end of the request.
- Expanded the `extractions` model with orchestration fields (`current_stage`, `retry_count`, `submitted_at`, `review_required`, `validation_decision`, `batch_id`, `idempotency_key`) and added Alembic migration `0003_add_orchestration_fields.py`.
- Added `backend/orchestration/service.py` as the job execution layer, including local background execution now and optional Celery queue hooks for production queue-based execution later.
- Added `GET /api/jobs/{job_id}` for job-state tracking and updated `/api/results/{job_id}` so it now reports in-progress jobs cleanly instead of pretending results already exist.
- Added extractor stage callbacks so job state can progress through preprocessing, OCR, classification, extraction, and export stages while the background job is running.
- Added single-request idempotency-key reuse for extraction submission so repeated client retries can return the same queued job instead of creating duplicate work.
- Updated deletion behavior so removing an extraction also removes the durable raw upload and its `documents` row, preventing storage leaks after the async shift.
- Added environment knobs and dependency declarations for the orchestration backend (`JOB_EXECUTION_BACKEND`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `celery`, `redis`) and exposed async-job capability in the status endpoint.
- Verified the modified Python modules with `python -m compileall` for the updated API, orchestration, extractor, and DB model files.
- Implemented Phase 3 workflow validation integration by adding `backend/validation_service.py` as the shared runtime for validation execution, DB persistence, report summarization, and validation-to-job-decision mapping.
- The async extraction worker now runs validation automatically after extraction, stores a validation report, writes a `validation_summary` into extraction metadata, and sets `validation_decision` on the job before finalizing the terminal job status.
- Final job routing is now validation-aware: extraction results can be promoted to `needs_review` or `low_confidence` based on validation confidence and validation errors instead of relying only on extraction-side heuristics.
- Updated the manual validation API routes to reuse the same shared validation persistence and decision logic as the async worker, so background and on-demand validation now follow one consistent backend path.
- Updated `/api/jobs/{job_id}` and `/api/results/{job_id}` to return validation summary data so clients can see why a job completed, why it needs review, or why it was marked low confidence.
- Added validation decision thresholds in configuration (`VALIDATION_PASS_MIN_CONFIDENCE`, `VALIDATION_LOW_CONFIDENCE_SCORE`) so review routing can be tuned without code changes.
- Verified the Phase 3 Python modules with `python -m compileall` for `backend/validation_service.py`, validation routes, orchestration service, response models, validator logic, and related route files.
- Implemented Phase 4 observability in `backend/observability.py`, including lightweight runtime counters, stage-timing aggregation, failure-category tracking, dependency-aware readiness checks, and a machine-readable metrics snapshot written to `outputs/metrics/runtime_pipeline_metrics.json`.
- Wired request metrics into `backend/api/middleware/request_context.py` so API traffic now records request counts, path/method/status breakdowns, and average/max request duration.
- Wired orchestration metrics into `backend/orchestration/service.py` so job submissions, stage transitions, final statuses, validation decisions, processing times, and failure categories are all tracked during real workflow execution.
- Improved failure categorization so the runtime metrics can distinguish extraction failures, validation failures, persistence failures, and general workflow failures instead of collapsing them into one undifferentiated error bucket.
- Replaced the old superficial health endpoint with production-shaped health surfaces in `backend/api/routes/health.py`: `GET /api/health/live`, `GET /api/health/ready`, `GET /api/health`, `GET /api/metrics`, and an expanded `GET /api/status`.
- Readiness now checks database connectivity, job backend availability, storage directories, OCR availability, and LLM configuration instead of only reporting import-level health.
- Exposed async-job and observability capability cleanly in the OpenAPI auth exclusions and status payload so these support endpoints remain usable without misleading authentication requirements in Swagger.
- Added `METRICS_DIR` creation in configuration so runtime metrics snapshots have a durable output location under `outputs/metrics`.
- Verified the Phase 4 modules with `python -m compileall` for the observability service, request middleware, health routes, API main file, extraction route, orchestration service, and config module.

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

### 2026-03-12
- Added centralized API error helpers so unexpected backend failures now return sanitized error payloads instead of raw exception text.
- Added request context middleware that assigns an `X-Request-ID` to every request, returns it in the response, and logs request method/path/status/duration for easier incident tracing.
- Added default security response headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`) and `Cache-Control: no-store` on auth endpoints.
- Switched global exception handling to consistent JSON error envelopes for `HTTPException`, request validation errors, and unhandled server exceptions.
- Replaced route-level `500` responses that exposed `str(exception)` in extraction, results, and validation endpoints with generic internal-server-error responses while keeping full details in server logs.
- Reduced production log sensitivity by disabling Loguru backtraces/diagnostics unless `DEBUG_MODE=True`.
- Added new environment toggles in `.env.example` for sanitized error detail exposure, request-id header naming, security headers, and optional HSTS.
- Optimized OCR pass selection so high-confidence pages stop after the fast dense-text modes instead of always paying for an extra sparse-text retry.
- Added configurable scanned-PDF performance controls for render DPI, PDF render threads, and per-page OCR worker count.
- Added cached `ocr_run_summary` metadata with page count, average OCR confidence, engine usage, per-page timings, and worker count so performance analysis can reuse the latest OCR run.
- Enabled PaddleOCR fallback for low-confidence non-Gujarati pages when PaddleOCR is installed, improving recovery options for hard OCR cases without slowing the fast path.
- Avoided duplicate scanned-PDF metadata work by reusing the latest OCR summary and using `pdfinfo_from_path` when a fallback page count is needed.
- Extended `tests/baseline_benchmark.py` to report P50/P95 runtime, average OCR page confidence, average OCR workers used, and OCR engine usage totals.
- Ran a full `test_images` corpus diagnostic pass and saved detailed runtime/OCR summaries to `outputs/metrics/current_perf_diagnostics.json` and `outputs/metrics/current_perf_diagnostics_after_tuning.json`.
- Added an OCR image-size cap (`MAX_OCR_IMAGE_PIXELS`, default `3,000,000`) so very large RGBA images are downscaled to a bounded working size before Tesseract runs.
- Tightened low-confidence recovery so targeted-language retry and aggressive preprocessing are skipped for already-dense outputs where those extra passes were expensive and not improving confidence.
- Verified the tuning on the full `test_images` corpus: average runtime improved from `23.53s` to `15.90s`, average `extract_text` time improved from `21.46s` to `13.85s`, P95 runtime dropped from `50.36s` to `23.96s`, and average OCR confidence increased from `80.06%` to `81.36%`.
- Verified the two worst outliers individually: `Gemini_Generated_Image_nmtcfynmtcfynmtc.png` dropped from `116.06s` to `45.78s`, and `Gemini_Generated_Image_oohwmdoohwmdoohw.png` dropped from `50.36s` to `23.00s`.
- Hardened the Mistral client path with configurable request timeout, bounded retries, and backoff so classifier/extraction calls fail fast instead of hanging or silently defaulting.
- Added rule-based classification fallback in `backend/ai_agent.py` with explicit `classification_source`, `classification_status`, and disagreement metadata so LLM outages no longer quietly label documents as `other`.
- Stopped retrying schema extraction when classification already proved the LLM was unavailable; the pipeline now exits that path early and marks the result for review instead of wasting more time on calls that cannot succeed.
- Added review-state gating in `backend/extractor.py` so weak outputs are now marked as `needs_review` or `low_confidence` using OCR confidence, document quality, classification certainty, and schema coverage signals.
- Updated extraction persistence so review outcomes are stored distinctly in the database as `completed_review` and `completed_low_confidence` instead of being mixed into `completed` or `failed`.
- Expanded image quality assessment in `backend/extractors/preprocessor.py` to score blur, contrast, brightness, background noise, edge density, skew, foreground ratio, transparency, and overall document difficulty before OCR starts.
- Passed pre-OCR quality context into the OCR engine so hard documents can trigger stronger recovery behavior instead of using the same OCR path as clean scans.
- Added layout-aware OCR fallback in `backend/extractors/ocr_extractor.py` that detects text regions, OCRs cropped regions separately, and keeps the layout result when it improves confidence on difficult documents.
- Added a local Paddle runtime home under `outputs/paddle_runtime` and disabled PaddleX host checks by default so PaddleOCR can initialize cleanly inside the project `venv` without trying to write to blocked user-profile paths.
- Verified the new accuracy-safety path with real smoke tests on 2026-03-12: `test_invoice_english_1772825371308.png` now falls back to heuristic `invoice` classification in `11.69s` and is correctly marked `needs_review` instead of appearing fully successful when the LLM is down.
- Verified the hard-document OCR escalation on 2026-03-12: `Gemini_Generated_Image_nmtcfynmtcfynmtc.png` now switches to `tesseract_layout`, improving OCR confidence from `55.12%` to `57.19%` while keeping the result flagged `needs_review`.
- Verified module health with `python -m compileall` for the modified backend files and confirmed that importing `backend/extractors/ocr_extractor.py` from `venv\Scripts\python.exe` now reports `HAS_PADDLEOCR=True`.
- Fixed the PaddleOCR runtime mismatch on 2026-03-12 by pinning a working stack in the project `venv` and `requirements.txt`: `paddleocr==3.2.0`, `paddlepaddle==3.1.1`, `paddlex>=3.2.0,<3.3.0`, `pypdfium2==4.30.0`, and `protobuf<7.0`.
- Updated the PaddleOCR adapter so it works with the current API shape (`predict(...)` or `ocr(...)`) and can parse both newer dict-style results and older tuple-style results.
- Improved OCR engine selection so the pipeline no longer compares engines only by raw confidence. It now also scores text usefulness, garbage-text signals, and document-pattern hints before choosing between Tesseract, layout OCR, PaddleOCR, or EasyOCR.
- Added a smarter PaddleOCR trigger for dense English business documents, so invoices and bank statements can use PaddleOCR even when Tesseract is already readable but not actually the best result.
- Re-ran real OCR validation on 2026-03-12 after the Paddle fix:
  - `test_invoice_english_1772825371308.png`: final engine changed from Tesseract to PaddleOCR (`89.56%` -> `98.06%`, `1090` -> `1128` chars).
  - `test_bank_statement_1772825402638.png`: final engine changed from Tesseract to PaddleOCR (`85.12%` -> `98.43%`, `601` -> `847` chars).
  - `test_marksheet_hindi_1772825386762.png`: Tesseract correctly remained the winner (`88.98%`) instead of switching to PaddleOCR.
  - `Gemini_Generated_Image_nmtcfynmtcfynmtc.png`: layout OCR correctly remained the winner (`57.19%`) because PaddleOCR produced weaker output on that hard noisy image.
- Confirmed an environment caveat on 2026-03-12: PaddleOCR inference works in the real project `venv`, but sandboxed runs may still fail to fetch model files if they are not already cached locally.
- Expanded step 8 testing on 2026-03-12 by adding a reusable sample manifest at `tests/baseline_sample_manifest.json` and extending `tests/baseline_benchmark.py` so the benchmark now reports sample tags, final OCR engine by file, review-needed files, review reasons, and a machine-readable `outputs/metrics/baseline_metrics_detailed.json`.
- Ran the broader local sample audit on 2026-03-12 across all 19 currently available sample files and wrote the report to `outputs/metrics/baseline_metrics.md`.
- The broader audit currently shows:
  - 19 files tested
  - 15 `success`
  - 3 `needs_review`
  - 1 `low_confidence`
  - 0 hard failures
  - final OCR engine split: 14 `tesseract`, 4 `paddleocr`, 1 `tesseract_layout`
- The current files still needing attention after the broader audit are:
  - `hindi_resume.png` (`low_confidence`)
  - `Gemini_Generated_Image_nmtcfynmtcfynmtc.png` (`needs_review`)
  - `Gemini_Generated_Image_oohwmdoohwmdoohw.png` (`needs_review`)
  - `Gemini_Generated_Image_tukltxtukltxtukl.png` (`needs_review`)
- The broader audit also exposed one useful gap: the quality pre-check currently labels all 19 files as `easy`, which means the document-difficulty scoring still needs improvement for hard noisy cases.

### 2026-03-16
- Finished the main frontend integration pass in `frontend/` by aligning the generated React screens to the real backend contracts instead of the Figma mock payloads.
- Normalized the frontend data flow for jobs, results, reviews, uploads, and system health so the UI now consumes the actual backend shapes returned by `/api/extractions`, `/api/jobs/{id}`, `/api/results/{id}`, `/api/reviews`, `/api/reviews/{id}`, `/api/health`, and `/api/status`.
- Fixed review actions to use the real backend decision API (`corrected`, `accept_original`, `accept_ai_proposal`) and send the required resolve payload for review-case completion.
- Reworked result downloads to use the authenticated backend download endpoint through the API client instead of linking directly to stored artifact paths, which would fail with bearer-token auth.
- Updated the job-detail timeline to use the real orchestration stage names (`quality_assessment`, `text_extraction`, `document_classification`, `structured_extraction`, `persist_outputs`, `audit_validation`) while preserving the product-facing labels in the UI.
- Cleaned the last generated frontend issues that were blocking shipping quality: missing Vite env typing, page-level type mismatches, and visible text/encoding artifacts in the generated screens.
- Verified the frontend with a full production build on 2026-03-16: `npm run build` in `frontend/` completed successfully and emitted a production bundle under `frontend/dist`.
- Fixed a runtime backend submission bug in `backend/api/routes/extraction.py` where single-file upload queueing accessed `extraction.id` after the ORM instance was detached, causing `DetachedInstanceError` and a `500` on `/api/extract`.
- Tightened validator filtering in `backend/agents/validator/logic.py` so legitimate archived invoice dates are no longer flagged as `date_parse_uncertain` just because they are older than the current system date.
- Improved result-page readability in `frontend/src/features/results/ResultPage.tsx` by replacing the raw JSON-style structured data dump with recursive structured rendering and by expanding flagged-field presentation to show extracted and proposed values more clearly.
- Hardened frontend data-loading behavior by increasing query retry resilience in `frontend/src/app/providers/Providers.tsx` and adding retry actions to jobs, dashboard, result, and review queue failure states so transient API hiccups do not immediately degrade the UI.
- Re-verified the runtime-fix pass on 2026-03-16 with `python -m py_compile` for the touched backend routes and another successful `npm run build` for `frontend/`.
- Stabilized local API responsiveness on 2026-03-16 by changing `backend/orchestration/service.py` so local extraction jobs start on detached daemon threads instead of staying tied to FastAPI background-task flow. This reduces the chance that heavy OCR/validation work starves the same dev server that the frontend is polling.
- Simplified frontend job-list loading by moving `frontend/src/lib/api/jobsApi.ts` from the heavier `/api/extractions` listing path to the lighter `/api/jobs` endpoint, and expanded the backend job-status payload to include filename, document type, and confidence fields so the UI still has the metadata it needs.
- Updated `backend/api/main.py` so its module entrypoint no longer hardcodes `reload=True`; it now respects `DEBUG_MODE`, which is safer for local QA and less likely to worsen shutdown behavior on Windows.
- Re-verified the stability pass on 2026-03-16 with `python -m py_compile` for the touched backend files and another successful `npm run build` for `frontend/`.
- Refactored the frontend information architecture on 2026-03-16 so `Dashboard` is now a focused operations overview while `Jobs` became the full paginated history/workspace, removing the previous duplication between those pages.
- Added a glassmorphism-based shared UI foundation in `frontend/src/styles/globals.css`, `frontend/src/components/layout/AppShell.tsx`, `frontend/src/components/layout/Sidebar.tsx`, and the new `PageLayout`/`Pagination`/`DataPreview` components so the app now uses one consistent layout rhythm, card treatment, and readable nested-data presentation.
- Rebuilt the main workspace pages as structured operator views:
  - `DashboardWorkspacePage.tsx`
  - `JobsWorkspacePage.tsx`
  - `JobTimelinePage.tsx`
  - `ResultWorkspacePage.tsx`
  - `ReviewQueueWorkspacePage.tsx`
  - `ReviewCaseWorkspacePage.tsx`
  - `SystemWorkspacePage.tsx`
  These now expose real backend stages more transparently, center the system-health layout properly, add 15-item pagination to dense queues, and present review/result values in a human-readable way instead of raw `[object Object]` output.
- Improved perceived UX quality by adding animated tab-panel transitions, stronger empty/error states, clearer calls to action, and review/detail layouts that keep extracted values, AI suggestions, and human corrections readable side by side.
- Re-verified the UX refactor on 2026-03-16 with another successful `npm run build` in `frontend/` after the new page modules and shared components were wired into the router.

### 2026-03-21
- Tightened frontend consistency on the current UI baseline without changing the restored visual direction.
- Fixed `frontend/src/features/jobs/JobDetailPage.tsx` so queued jobs with no active backend stage no longer incorrectly highlight `Preprocessing` as in-progress. Successful terminal jobs still show all stages complete, but the branch logic is now explicit and easier to maintain.
- Improved live data consistency on `Dashboard` and `Jobs` by enabling automatic 5-second refresh while any listed job is still non-terminal. This reduces stale tables when users stay on those pages during active processing.
- Standardized the list fetch size used by `Dashboard` and `Jobs` to `200`, which reduces obvious stat drift and keeps both pages aligned on the same dataset window during local QA.
- Tightened type safety in `frontend/src/features/results/ResultPage.tsx` by using the shared `RecoveryAttempt` model for recovery rendering and by making the recovery tab show a real loading state only while the request is actually in flight.
- Cleaned `frontend/src/app/providers/Providers.tsx` to use `axios` error typing instead of ad-hoc status casting in the retry predicate.
- Verified the consistency pass on 2026-03-21 with a successful `npm run build` in `frontend/`.
- Fixed a follow-up jobs-list regression on 2026-03-21 by aligning `backend/api/routes/jobs.py` with the frontend list window. The route now allows `limit` values up to `200`, matching the current dashboard/jobs requests and preventing those pages from failing with validation errors instead of returning data.
- Verified the backend route fix on 2026-03-21 with `python -m py_compile backend/api/routes/jobs.py`.
- Hardened frontend reliability on 2026-03-21 so route switches and temporary backend hiccups do not leave the UI stuck in stale error states:
  - `frontend/src/app/providers/Providers.tsx` now forces query recovery on remount, reconnect, and window focus, with retry-on-mount enabled and a shorter global staleness window.
  - `frontend/src/features/dashboard/DashboardPage.tsx`, `frontend/src/features/jobs/JobsPage.tsx`, and `frontend/src/features/reviews/ReviewQueuePage.tsx` now auto-retry when their queries are in an error state instead of waiting indefinitely for a manual refresh or full server restart.
- Implemented explicit client-side session lifecycle handling on 2026-03-21:
  - `frontend/src/lib/auth/tokenStore.ts` now tracks access-token expiry metadata and emits token-change notifications.
  - `frontend/src/lib/auth/AuthContext.tsx` now silently refreshes the session before access-token expiry and clears the session cleanly when refresh fails or the session expires.
  - `frontend/src/lib/api/client.ts` now preserves expiry metadata during interceptor-driven token refresh.
- Verified the frontend reliability/session pass on 2026-03-21 with a successful `npm run build` in `frontend/`.
- Optimized `backend/api/routes/jobs.py` on 2026-03-21 after runtime logs showed `/api/jobs` requests taking 40–200 seconds. The route was doing per-row `review_case` and `recovery_attempt` lookups, which scaled poorly for larger lists. It now bulk-loads open review-case ids and recovery counts for the whole page in two grouped queries instead of issuing those lookups inside the response loop.
- Verified the jobs-route performance patch on 2026-03-21 with `python -m py_compile backend/api/routes/jobs.py`.
- Started the frontend IA cleanup on 2026-03-21 with a dashboard-only refactor instead of a broad redesign:
  - added `frontend/src/features/dashboard/DashboardOverviewPage.tsx` as the new dashboard source of truth
  - switched routing in `frontend/src/app/router/router.tsx` so `/` and `/dashboard` now render the overview page instead of the old jobs-table dashboard
  - removed `System` from the primary sidebar navigation in `frontend/src/components/layout/Sidebar.tsx`
- The new dashboard now focuses on overview content only: KPI cards, processing snapshot, quick actions, recent activity, and review spotlight. The full jobs list remains owned by `/jobs`.
- Verified the dashboard/nav refinement on 2026-03-21 with a successful `npm run build` in `frontend/`.
- Refined the `Jobs` workspace on 2026-03-21 so it behaves as the single operational jobs page:
  - removed document-type filtering from `frontend/src/features/jobs/JobsPage.tsx`
  - made the top summary tiles interactive so `All Jobs`, `Active`, `Needs Review`, and `Completed` now act as status filters
  - defined `Active` as queued + processing workload instead of only `processing`
  - improved the page structure with a clearer filter bar, stronger empty/error states, and a more explicit workspace header
- Added a restrained glass treatment to the existing dark theme without changing the overall layout:
  - softened `card`, `input-base`, and `btn-secondary` surfaces in `frontend/src/styles/globals.css`
  - applied the same restrained glass surface to the sidebar shell in `frontend/src/components/layout/Sidebar.tsx`
- Verified the Jobs/glass refinement on 2026-03-21 with a successful `npm run build` in `frontend/`.
- Refined `frontend/src/features/jobs/JobDetailPage.tsx` on 2026-03-21 so the job-detail experience explains the real backend pipeline more clearly instead of only showing raw stage labels:
  - added stage descriptions for preprocessing, OCR, classification, structured extraction, persist outputs, and validation
  - added summary panels for current state, review routing, and pipeline mode
  - improved the live-tracking footer and active-stage treatment so operators can tell whether a job is queued, actively refreshing, terminal, or routed for review
- Verified the job-detail refinement on 2026-03-21 with a successful `npx tsc -b` in `frontend/`. A full Vite build in this shell still hits a local `esbuild` spawn permission issue, so TypeScript compilation was used to confirm the page changes.
- Refined `frontend/src/features/results/ResultPage.tsx` on 2026-03-21 so the result view is readable and workflow-aware instead of behaving like a raw payload dump:
  - replaced the embedded object renderer with the shared `DataPreview` component for structured values and flagged-field values
  - added summary cards for extraction coverage, validation confidence, and review routing
  - surfaced review-case field data directly inside the validation tab when a review case exists, with a direct `Open review case` CTA
  - improved recovery visibility by showing weak fields and improvement scores when recovery attempts exist
  - improved downloads feedback with per-format spinner states during file download
- Verified the result-page refinement on 2026-03-21 with another successful `npx tsc -b` in `frontend/`.
- Added a frontend motion polish pass on 2026-03-21 without changing the established visual language:
  - `frontend/src/components/layout/AppShell.tsx` now animates protected-route page transitions using a keyed wrapper tied to the current pathname
  - `frontend/src/styles/globals.css` now defines lightweight page-entry and tab-panel animations plus smoother button/input/card transitions
  - `frontend/src/features/results/ResultPage.tsx` now animates tab-content swaps instead of switching panels abruptly
  - included reduced-motion handling so the transitions degrade cleanly for users who prefer less motion
- Verified the motion polish pass on 2026-03-21 with another successful `npx tsc -b` in `frontend/`.
- Refined `frontend/src/features/reviews/ReviewCasePage.tsx` on 2026-03-21 so the human-review workflow is readable instead of flattening all field values into raw strings:
  - added summary cards for open fields, review progress, and AI suggestion count
  - replaced raw string rendering of extracted/proposed/corrected values with the shared `DataPreview` component
  - made field cards more structured, with dedicated sections for extracted value, AI proposal, and final corrected value
  - cleaned the action area so correction, AI acceptance, and original-value acceptance read as one coherent review control block
- Verified the review-case refinement on 2026-03-21 with another successful `npx tsc -b` in `frontend/`.
- Added source-document preview support for review workflows on 2026-03-21:
  - `backend/api/routes/review.py` now exposes an authenticated `GET /api/reviews/{review_id}/source` endpoint that streams the original uploaded document inline from the stored `Document.storage_uri`
  - `frontend/src/lib/api/reviewsApi.ts` now fetches that source file as a blob with filename and MIME metadata
  - `frontend/src/features/reviews/DocumentPreviewPane.tsx` now renders a sticky review-side preview pane with:
    - image preview + zoom controls
    - PDF preview using the browser's built-in viewer
    - retry and unsupported-file fallback states
  - `frontend/src/features/reviews/ReviewCasePage.tsx` now uses a split review workspace: document preview on the left, field decisions on the right
- Verified the review-preview pass on 2026-03-21 with `python -m py_compile backend/api/routes/review.py` and another successful `npx tsc -b` in `frontend/`.
- Improved review-field interaction flow on 2026-03-21 inside `frontend/src/features/reviews/ReviewCasePage.tsx`:
  - added selected-field state so one flagged field is always the current focus
  - auto-selects the first open field and automatically falls forward when the current field is no longer open after refresh
  - selected field cards now get stronger visual emphasis with a clear `Currently reviewing` badge
  - selected cards smoothly scroll into view and auto-focus the correction input for faster keyboard-driven review
  - added a compact current-focus summary block above the field list so operators always know which field they are reviewing
- Verified the review-interaction pass on 2026-03-21 with another successful `npx tsc -b` in `frontend/`.
- Refined the review queue and upload flows on 2026-03-22 so the remaining operator entry points are more purposeful and resilient:
  - `frontend/src/features/reviews/ReviewQueuePage.tsx` now behaves like a triage workspace instead of a plain table:
    - summary cards for open cases, in-progress cases, resolved cases, and total open fields
    - quick status filtering from both the cards and filter chips
    - search by file name, case id, job id, or document type
    - stronger row hierarchy with job-id context under each file name
  - `frontend/src/features/upload/SingleUploadPage.tsx` and `frontend/src/features/upload/BatchUploadPage.tsx` now show clearer submission-state UX:
    - pre-submit state cards
    - in-flight upload messaging
    - clearer validation feedback and ready/uploading indicators
- Added route-level failure UX on 2026-03-22:
  - `frontend/src/app/router/RouteErrorPage.tsx` now provides a controlled fallback for route/render failures
  - `frontend/src/app/router/router.tsx` now wires `errorElement` into login, protected routes, and the app shell
- Verified the review-queue/upload/error-boundary pass on 2026-03-22 with another successful `npx tsc -b` in `frontend/`.
- Refined the dashboard experience on 2026-03-22 into a richer, more product-defining operations overview without changing the established dark/indigo UI language:
  - added `frontend/src/features/dashboard/DashboardLandingPage.tsx` as the new dashboard source of truth
  - upgraded the top of the page into a control-tower style overview with live signal badges, focus cards, and direct workflow entry points
  - replaced the flatter old summary composition with stronger sections for control signals, pipeline lanes, recent activity, and review spotlight
  - switched `frontend/src/app/router/router.tsx` so `/` and `/dashboard` now use the richer dashboard implementation while leaving the jobs/reviews workspaces unchanged
- Verified the dashboard refinement on 2026-03-22 with `npx tsc -b` in `frontend/`.
- Refined `frontend/src/features/jobs/JobsPage.tsx` on 2026-03-23 so background polling is quieter and more stable:
  - the visible jobs count no longer flips between a count message and `Refreshing...` during auto-sync
  - background refetch now appears as a subtle `Syncing` indicator while keeping the current table data visible
  - the page now distinguishes between initial hard-load failures and background sync attempts more cleanly by only showing the full error state when no job data is available yet
- Verified the jobs refresh-state refinement on 2026-03-23 with `npx tsc -b` in `frontend/`.
- Reduced unnecessary frontend API churn on 2026-03-23:
  - removed background polling from `frontend/src/features/jobs/JobsPage.tsx`
  - removed background polling from `frontend/src/features/dashboard/DashboardLandingPage.tsx`
  - removed background polling from `frontend/src/features/reviews/ReviewQueuePage.tsx`
  - disabled focus-based auto-refetch on those workspace pages so they now fetch on entry and manual refresh instead of continuously polling in the background
  - kept live polling only on the single-job detail page, where stage-by-stage progress tracking actually needs it
- Verified the polling reduction pass on 2026-03-23 with `npx tsc -b` in `frontend/`.
- Improved jobs-table action discoverability on 2026-03-23 by making the row actions in `frontend/src/features/jobs/JobsPage.tsx` always visible instead of hover-only.
- Verified the jobs action-visibility refinement on 2026-03-23 with `npx tsc -b` in `frontend/`.

### 2026-03-28
- Completed the first backend refinement pass focused on API contract quality, review payload usability, validation summary clarity, weak-document deterministic cleanup, prioritization metadata, and legacy route/helper drift reduction.
- Cleaned the terminal result contract in `backend/api/routes/results.py` by:
  - removing the old `sys.path` injection hack
  - switching `GET /api/results/{extraction_id}` to the explicit `ResultResponse` model
  - adding `file_name`, `doc_type`, `review_priority`, `review_open_field_count`, and `unresolved_review_fields` directly to the result payload
  - preserving existing terminal result behavior for both complete and missing-result cases while making the payload more frontend-friendly
- Improved review payload shaping in `backend/review/service.py`:
  - added `get_open_review_case_snapshot(...)` so jobs/results can reuse one consistent open-review summary instead of separate ad hoc lookups
  - enriched review list/detail responses with frontend-friendly aliases (`id`, `file_name`, `doc_type`, `status`) plus `updated_at`, `critical_open_field_count`, `age_bucket`, `priority_score`, `resolved_field_count`, and `next_recommended_field`
  - tightened review-field ordering so unresolved critical fields rise to the top before lower-priority items
  - added human-readable `display_label`, `ui_message`, and field-level `priority_score` values for review fields
  - compacted verbose validation/evidence text so reviewer-facing payloads are shorter and less contradictory
- Tightened validation-summary output in `backend/validation_service.py` so `review_reasons` are now deduplicated, compacted, and trimmed instead of surfacing long raw validator text directly.
- Added deterministic weak-document cleanup in `backend/ai_agent.py` before any LLM repair path runs:
  - `payslip` extraction now normalizes numeric totals, cleans duplicate/blank earning/deduction rows, and derives `payslip_month` from `pay_period` when possible
  - `balance_sheet` extraction now normalizes section totals and removes blank/duplicate rows inside assets and liabilities sections before inconsistency checks
  - this keeps the existing repair hooks but reduces avoidable weak outputs before escalating to the repair prompt
- Improved job-status review metadata in `backend/api/routes/jobs.py` so `/api/jobs` and `/api/jobs/{id}` now expose `review_priority` and `review_open_field_count` from one shared snapshot path instead of leaving those fields empty.
- Impact on production readiness:
  - frontend no longer has to guess as much about review/result state
  - review payloads are more operator-friendly and easier to prioritize
  - weak document outputs are slightly more stable before expensive repair/review paths run
  - the backend result surface is cleaner and less legacy-coupled than before
- Verified on 2026-03-28 with `python -m py_compile` for:
  - `backend/api/models/responses.py`
  - `backend/review/service.py`
  - `backend/validation_service.py`
  - `backend/api/routes/results.py`
  - `backend/api/routes/jobs.py`
  - `backend/ai_agent.py`
- Added a dedicated automated QA scaffold under `QA/` instead of extending the legacy `tests/` folder:
  - `QA/backend/` now contains a real `pytest`-style smoke/integration suite with:
    - `conftest.py` for environment-driven API base URL, credentials, readiness checks, auth-token fixtures, and sample-file handling
    - `test_auth_and_health.py` for health/status/login/refresh/me coverage
    - `test_workflow_smoke.py` for optional upload -> job -> result -> review lifecycle coverage
    - `helpers.py` for job polling until terminal state
    - `pytest.ini` with `smoke` and `integration` markers
  - `QA/frontend/` now contains a Playwright scaffold with:
    - `playwright.config.ts`
    - `login.spec.ts`
    - `navigation.spec.ts`
    - `upload.spec.ts`
  - `QA/README.md` and `QA/.env.example` now document how to run both suites and which environment variables are required
- Impact on production readiness:
  - automated QA is now organized separately from the old ad hoc scripts
  - backend smoke coverage can be added immediately with `pytest`
  - frontend browser-flow automation now has a dedicated home for login/navigation/upload regression coverage
- Verified on 2026-03-28 with no-write compile checks for:
  - `QA/backend/conftest.py`
  - `QA/backend/helpers.py`
  - `QA/backend/test_auth_and_health.py`
  - `QA/backend/test_workflow_smoke.py`

### 2026-03-29
- Completed 5 production-readiness improvements to the frontend:
  - **Global toast notification system:** Created `frontend/src/components/ui/Toast.tsx`, `frontend/src/components/ui/ToastProvider.tsx`, and `frontend/src/lib/hooks/useToast.ts`. The `ToastProvider` wraps the entire app via `frontend/src/app/providers/Providers.tsx` and renders a capped bottom-right toast stack (auto-dismissed after 4s). All review workflow mutations in `frontend/src/features/reviews/ReviewCasePage.tsx` (correct field, accept AI proposal, accept original, resolve case) now fire descriptive success and error toasts instead of silently updating.
  - **Upload experience polish:** Rewrote `frontend/src/features/upload/SingleUploadPage.tsx` — on submit success, a `submitted` flash state adds a green "Job created ✓" banner and updates the Submission state card before redirecting after 900ms instead of navigating immediately. Rewrote `frontend/src/features/upload/BatchUploadPage.tsx` — adds a file extension pill per row (PDF/PNG/etc.), per-file status badges that animate to "Queued…" during upload and update to "Done ✓" on success, an animated progress bar during submission, a green "Batch accepted — N jobs queued" success banner before navigating to `/jobs`, and the X remove button is disabled during active upload.
  - **Extracted shared `UploadStateCard`:** Created `frontend/src/components/ui/UploadStateCard.tsx` to eliminate the identical component that was copy-pasted in both upload pages.
  - **Global React error boundary:** Created `frontend/src/components/ui/ErrorBoundary.tsx` (class component) and wired it as the outermost wrapper in `frontend/src/main.tsx`. Uncaught render errors in any lazy-loaded page now show a full-screen fallback with a reload button instead of a blank app.
  - **Dead file cleanup:** Deleted 716 lines of unreachable code that was using stale design tokens (`glass-panel`, `page-shell`, `page-container`) not present in the current design system: `features/dashboard/DashboardOverviewPage.tsx` (426 lines), `features/jobs/JobTimelinePage.tsx` (290 lines), `components/layout/PageLayout.tsx` (34 lines).
  - Added `fadeSlideIn` keyframe to `frontend/src/styles/globals.css` for smooth toast entrance animations.
- Verified on 2026-03-29 with `npx tsc -b --noEmit` in `frontend/` — exit code 0, no type errors.
- Impact: mutations across the review workflow now have explicit operator feedback; upload experience is significantly more informative and forgiving; render-level crashes no longer produce a blank screen; 716 lines of dead code removed from the codebase.

- Completed a product-level frontend refinement pass focused on the first five UX themes: clearer information architecture, more operator-centric workflows, stronger state communication, shared design-system primitives, and better perceived polish.
- Added shared layout/state primitives:
  - `frontend/src/components/layout/PageHeader.tsx` for consistent page eyebrow/title/subtitle/action composition
  - `frontend/src/components/ui/StatePanel.tsx` for standardized loading, empty, error, and success surfaces
  - extended `frontend/src/styles/globals.css` with shared page-shell, section-frame, and badge classes so core screens now feel related instead of individually assembled
- Replaced the routed dashboard surface with `frontend/src/features/dashboard/DashboardCommandPage.tsx` and updated `frontend/src/app/router/router.tsx` to use it for `/` and `/dashboard`.
  - The dashboard now behaves like a real command center rather than a second jobs page
  - It emphasizes workload, review pressure, quick actions, and recent activity instead of duplicating the operational table
- Replaced the routed review queue surface with `frontend/src/features/reviews/ReviewQueueTriagePage.tsx` and updated routing for `/reviews`.
  - The queue is now triage-first instead of table-first
  - It surfaces “review first”, stronger urgency cues, clearer metrics, and more readable case cards with next-action context
- Replaced the routed result surface with `frontend/src/features/results/ResultInsightsPage.tsx` and updated routing for `/jobs/:id/result`.
  - The result page now chunks the experience into structured data, validation, review linkage, downloads, timings, and recovery
  - This makes the page more operator-readable and reduces the feeling of one long mixed-content slab
- Extended frontend model/API handling so the new backend review metadata is actually used:
  - richer review/result/job fields were added to `frontend/src/types/models.ts`
  - `frontend/src/lib/api/resultsApi.ts`, `frontend/src/lib/api/reviewsApi.ts`, and `frontend/src/lib/api/jobsApi.ts` now normalize the new review status, priority, unresolved-field, and summary metadata instead of dropping it
- Impact on production readiness:
  - the primary routed pages now have clearer responsibilities and less overlap
  - state handling is more consistent across loading, error, and empty conditions
  - the app reads more like one coherent operator console than a set of functional screens
  - visual hierarchy and action clarity are stronger without breaking the current dark/indigo theme
- Verified on 2026-03-29 with `npx tsc -b` in `frontend/`
- Rolled back the active `/reviews` route to the earlier `frontend/src/features/reviews/ReviewQueuePage.tsx` after the newer triage-style queue UI was judged worse than the previous version.
  - `frontend/src/app/router/router.tsx` now points `/reviews` back to `ReviewQueuePage`
  - the newer `ReviewQueueTriagePage.tsx` remains on disk but is no longer the active review queue surface
- Verified on 2026-03-29 with `npx tsc -b` in `frontend/`

## Current Next Steps
The next work should follow the locked implementation order in `BACKEND_EXECUTION_ROADMAP.md`.

### Immediate Priority Order
1. Run end-to-end frontend QA against the live backend for login, single upload, batch upload, job tracking, result viewing, review actions, and downloads.
2. Fix any runtime-only frontend issues that appear during QA, especially API edge cases that do not show up in the production build.
3. Run the full corpus benchmark with the current `test_images` set and review `outputs/metrics/baseline_metrics.md` plus `outputs/metrics/baseline_metrics_detailed.json`.
4. Build or use a resumable corpus runner for the real orchestration path so full end-to-end validation does not rely on one long inline shell command.
5. Restore Mistral connectivity and rerun a small shadow-mode validation on first-wave `invoice` and `bank_statement` files.
6. Compare recovery proposals against human review outcomes and tighten any acceptance rules that look unsafe.
7. Enable active recovery only after shadow-mode evidence shows the path is helping safely.

### Important Guardrails
- Do not create fake benchmark truth with hardcoded labels for unknown files.
- Do not make the entire system fully agentic before the orchestration layer is stable.
- Keep the main extraction and validation path deterministic.
- Add agentic behavior later only for bounded recovery or review assistance.

### Tracking Rule
- After every completed implementation step, update this tracker on the same day.
- Each entry should say what changed, why it mattered, and what was verified.
