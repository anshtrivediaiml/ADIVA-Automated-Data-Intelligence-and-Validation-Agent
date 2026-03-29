# Automated QA

This folder is the dedicated home for automated QA. It is separate from the
legacy ad hoc scripts under `tests/`.

## Structure

- `QA/backend/`
  - `pytest` smoke/integration tests against the running API
- `QA/frontend/`
  - Playwright browser-flow tests against the running frontend
- `QA/.env.example`
  - environment variables used by both suites

## Recommended usage

Run the application normally in two terminals:

```powershell
# Terminal 1
cd backend
..\venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend
npm run dev
```

Then run automated QA from the repo root.

## Backend QA

Install once in the project virtual environment:

```powershell
.\venv\Scripts\python.exe -m pip install pytest httpx
```

Run:

```powershell
.\venv\Scripts\python.exe -m pytest QA/backend -m smoke
```

Optional deeper lifecycle run:

```powershell
$env:QA_ENABLE_UPLOAD_FLOW="1"
$env:QA_EMAIL="your-email"
$env:QA_PASSWORD="your-password"
$env:QA_SAMPLE_FILE="test_images\\test_invoice_english_1772825371308.png"
.\venv\Scripts\python.exe -m pytest QA/backend -m integration
```

## Frontend QA

Install once inside `frontend/`:

```powershell
cd frontend
npm install -D @playwright/test
npx playwright install
```

Then run from repo root:

```powershell
cd frontend
$env:QA_EMAIL="your-email"
$env:QA_PASSWORD="your-password"
npx playwright test -c ..\\QA\\frontend\\playwright.config.ts
```

Optional upload flow:

```powershell
$env:QA_SAMPLE_FILE="C:\\full\\path\\to\\sample.png"
npx playwright test -c ..\\QA\\frontend\\playwright.config.ts --grep upload
```

## Notes

- Backend smoke tests are safe to start with immediately.
- Upload/result/review flows are intentionally opt-in because they depend on
  runtime OCR/AI availability and a real sample file.
- Frontend tests assume the dev server is already running.
