# ADIVA — Automated Data Intelligence & Validation Agent

> An AI-powered document intelligence platform for automated extraction, validation, and structured review of business documents.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-3ECF8E?logo=supabase&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

---

## Why ADIVA?

Manually processing business documents — invoices, purchase orders, receipts — is slow, error-prone, and doesn't scale. ADIVA replaces that with a fully automated pipeline: documents go in, structured and validated data comes out. When the AI isn't confident enough, documents are routed to a human review queue rather than silently producing bad data. The result is a system that's both automated and trustworthy.

---

## Architecture

![ADIVA Architecture](docs/architecture.png)

---

## What it does

ADIVA processes uploaded documents (PDF, images, DOCX, TIFF) through a full pipeline:

1. **OCR & Extraction** — Tesseract + PaddleOCR extract text and tables
2. **AI Classification & Parsing** — Mistral AI identifies the document type and extracts structured fields
3. **Validation** — confidence scoring, field-level quality checks, and rule-based validation
4. **AI Recovery** — low-confidence fields are re-attempted with alternative extraction strategies before escalating
5. **Review Queue** — documents that can't be recovered automatically enter a human review workflow
6. **Export** — results downloadable as JSON, CSV, or Excel

The frontend is a React operator console for managing jobs, reviewing flagged cases, and downloading results.

---

## How it handles failures

ADIVA doesn't silently drop bad extractions. The failure path is intentional:

```
Extraction → Validation
                 ↓ fails
            AI Recovery (retries with alternate strategies)
                 ↓ still fails
            Human Review Queue
                 ↓ resolved
            Final Output
```

The `ENABLE_AI_RECOVERY` flag controls whether recovery runs at all. `AI_RECOVERY_SHADOW_MODE` lets you run recovery in the background without affecting output — useful for monitoring recovery quality before fully relying on it.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend API** | FastAPI + Uvicorn |
| **Database** | PostgreSQL via Supabase |
| **AI / LLM** | Mistral AI (`mistral-large-latest`) |
| **OCR** | Tesseract + PaddleOCR 3.2.0 |
| **Table Extraction** | Camelot, img2table |
| **Task Execution** | Local threaded for dev, Celery + Redis for queued execution |
| **Frontend** | React 18, Vite, TanStack Query, React Router |
| **Styling** | Tailwind CSS (dark theme) |
| **Containerization** | Docker + Docker Compose + Nginx |

---

## Project Structure

```
ADIVA/
├── backend/
│   ├── api/            # FastAPI app (main.py = real entry point)
│   ├── agents/         # AI agent pipeline
│   ├── db/             # Models, migrations, seed scripts
│   ├── extractors/     # OCR + document extraction modules
│   ├── orchestration/  # Job dispatch and lifecycle
│   ├── recovery/       # AI recovery for low-confidence fields
│   ├── review/         # Review case management
│   ├── schemas/        # Pydantic models
│   ├── storage/        # File upload handling
│   ├── exporters/      # JSON, CSV, Excel export
│   ├── config.py       # All env var settings
│   └── main.py         # Thin Uvicorn launcher (dev use)
│
├── frontend/           # React operator console (Vite)
│   └── src/
│       ├── features/   # Jobs, Reviews, Upload, Dashboard, Results
│       ├── components/ # Shared UI components
│       ├── lib/        # API clients, hooks, utils
│       └── types/      # TypeScript models
│
├── alembic/            # Database migrations
├── docs/               # Architecture diagrams and assets
├── QA/                 # Playwright (frontend) + smoke tests (backend)
├── outputs/            # Runtime: uploads, results, logs (gitignored)
│
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── nginx.conf
├── requirements.txt
└── .env.example
```

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- Tesseract OCR installed and on PATH
- A Supabase project (free tier works)
- Mistral AI API key

### 1. Clone and set up environment

```bash
git clone <repo-url>
cd ADIVA

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt

 or 

uv init
uv add -r requirements.txt
```

### 2. Configure environment

```bash
copy .env.example .env
```

Edit `.env` and fill in at minimum:

```env
DATABASE_URL=postgresql+psycopg://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres?sslmode=require
MISTRAL_API_KEY=your_key_here
JWT_SECRET_KEY=any-strong-random-string
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your_password
```

### 3. Run database migrations and seed admin

```bash
alembic upgrade head
python backend/db/seed_admin.py
```

Sign in with the same `ADMIN_EMAIL` and `ADMIN_PASSWORD` values you put in `.env`.

### 4. Start in local mode (2 terminals)

This is the normal development flow and the default backend mode.

Make sure `.env` contains:

```env
JOB_EXECUTION_BACKEND=local
```

Terminal 1: backend API

```bash
cd backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2: frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

The Vite dev server proxies `/api` requests to `http://localhost:8000`.

### 5. Start in Celery mode (3 terminals)

Use this only when you want queued execution through Redis + Celery.

Make sure `.env` contains:

```env
JOB_EXECUTION_BACKEND=celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

Start Redis first. If Redis is not installed locally, you can run it with Docker:

```bash
docker run -d --name adiva-redis -p 6379:6379 redis:7-alpine
```

Terminal 1: backend API

```bash
cd backend
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2: frontend

```bash
cd frontend
npm install
npm run dev
```

Terminal 3: Celery worker

Run this from the `backend` folder:

```bash
cd backend
celery -A orchestration.tasks worker --loglevel=info --pool=solo
```

Notes:

- On Windows, keep `--pool=solo`.
- `/api/health` in Celery mode verifies both Redis and an active Celery worker.
- Stop local Redis later with `docker stop adiva-redis` and `docker rm adiva-redis`.

### Quick Start (PowerShell)

```powershell
.\start.ps1
```

This starts the same 2-terminal local flow from VS Code tasks:

- backend: `python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`
- frontend: `npm run dev`

---

## Execution Backends

- `local`: default for development. The API process starts background threads itself.
- `celery`: recommended for staging/production. The API enqueues jobs into Redis and a separate Celery worker processes them.

Keep both modes supported:

- use `local` for normal development and demos
- use `celery` for production-style queued execution

---

## Docker Deployment

### Prerequisites
- Docker Desktop

### Run with Docker

Normal mode:

```bash
docker compose up --build
```

App will be at `http://localhost` (port 80).

Celery mode:

```bash
docker compose --profile celery up --build
```

For Celery mode, set:

```env
JOB_EXECUTION_BACKEND=celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

The `celery` profile starts `redis` and `celery-worker` alongside `backend` and `frontend`.

### Required environment variables for Docker

Set these before running (or create a `.env` file at repo root):

```env
DATABASE_URL=...        # Supabase connection string
MISTRAL_API_KEY=...     # Mistral AI key
JWT_SECRET_KEY=...      # Strong random string (use: openssl rand -hex 32)
ADMIN_EMAIL=...
ADMIN_PASSWORD=...
CORS_ORIGINS=http://localhost
JOB_EXECUTION_BACKEND=local
```

> Alembic migrations run automatically on backend container startup.
> Uploaded files and results persist in a named Docker volume (`outputs`).
> In Celery mode, the backend and worker share that same volume so uploaded files and generated exports remain visible to both containers.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | Supabase Postgres connection string |
| `MISTRAL_API_KEY` | ✅ | — | Mistral AI API key |
| `JWT_SECRET_KEY` | ✅ | — | JWT signing secret |
| `ADMIN_EMAIL` | ✅ (first run) | — | Seed admin email |
| `ADMIN_PASSWORD` | ✅ (first run) | — | Seed admin password |
| `JOB_EXECUTION_BACKEND` | ❌ | `local` | `local` or `celery` |
| `ENABLE_AI_RECOVERY` | ❌ | `True` | Run AI recovery before falling back to human review |
| `AI_RECOVERY_SHADOW_MODE` | ❌ | `False` | Keep recovery active, not shadow-only |

For advanced internal tuning, see `backend/config.py`.

Celery-specific settings:

- `CELERY_BROKER_URL`: Redis broker URL used when `JOB_EXECUTION_BACKEND=celery`
- `CELERY_RESULT_BACKEND`: result backend URL used when `JOB_EXECUTION_BACKEND=celery`

---

## API Overview

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/login` | POST | Login, returns JWT |
| `/api/extract` | POST | Submit single document |
| `/api/extract/batch` | POST | Submit batch of documents |
| `/api/jobs` | GET | List all jobs with filters |
| `/api/jobs/{id}` | GET | Job status + metadata |
| `/api/results/{id}` | GET | Extraction result |
| `/api/results/{id}/download/{format}` | GET | Download as `json`, `csv`, `xlsx` |
| `/api/reviews` | GET | Review queue |
| `/api/reviews/{id}` | GET | Review case detail |
| `/api/reviews/{id}/resolve` | POST | Resolve review case |
| `/api/dashboard` | GET | Aggregated stats for dashboard |
| `/api/health` | GET | Health check (includes Redis/Celery in celery mode) |

Full interactive docs available at `http://localhost:8000/docs` when running locally.

---

## QA / Testing

```bash
# Backend unit + integration tests
pytest tests/

# Frontend (Playwright)
cd QA/frontend
npm install
npx playwright test

# Backend smoke tests
cd QA/backend
pytest
```

Set `QA_EMAIL`, `QA_PASSWORD`, and `QA_FRONTEND_URL` before running frontend tests.
