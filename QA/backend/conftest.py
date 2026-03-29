from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx
import pytest


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in {None, ""} else default


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return (_env("QA_API_BASE_URL", "http://127.0.0.1:8000/api") or "").rstrip("/")


@pytest.fixture(scope="session")
def frontend_base_url() -> str:
    return (_env("QA_FRONTEND_URL", "http://127.0.0.1:5173") or "").rstrip("/")


@pytest.fixture(scope="session")
def qa_timeout_seconds() -> int:
    return int(_env("QA_JOB_TIMEOUT_SECONDS", "180") or "180")


@pytest.fixture(scope="session")
def qa_poll_interval_seconds() -> int:
    return int(_env("QA_POLL_INTERVAL_SECONDS", "3") or "3")


@pytest.fixture(scope="session")
def http_client() -> httpx.Client:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def ensure_api_ready(http_client: httpx.Client, api_base_url: str) -> None:
    deadline = time.time() + 30
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = http_client.get(f"{api_base_url}/health")
            if response.status_code == 200:
                return
        except Exception as exc:  # pragma: no cover - readiness retry path
            last_error = exc
        time.sleep(1)
    pytest.fail(f"API did not become ready at {api_base_url}: {last_error}")


@pytest.fixture(scope="session")
def qa_credentials() -> dict[str, str]:
    email = _env("QA_EMAIL")
    password = _env("QA_PASSWORD")
    if not email or not password:
        pytest.skip("QA_EMAIL and QA_PASSWORD are required for authenticated QA.")
    return {"email": email, "password": password}


@pytest.fixture(scope="session")
def auth_tokens(
    http_client: httpx.Client,
    api_base_url: str,
    qa_credentials: dict[str, str],
) -> dict[str, Any]:
    response = http_client.post(f"{api_base_url}/auth/login", json=qa_credentials)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    return payload


@pytest.fixture(scope="session")
def auth_headers(auth_tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_tokens['access_token']}"}


@pytest.fixture(scope="session")
def sample_file_path() -> Path:
    sample = _env("QA_SAMPLE_FILE", "test_images\\test_invoice_english_1772825371308.png")
    path = Path(sample)
    if not path.exists():
        pytest.skip(f"Sample file not found: {path}")
    return path

