from __future__ import annotations

import time
from typing import Any

import httpx
import pytest


def poll_job_until_terminal(
    *,
    client: httpx.Client,
    api_base_url: str,
    auth_headers: dict[str, str],
    job_id: str,
    timeout_seconds: int,
    poll_interval_seconds: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        response = client.get(f"{api_base_url}/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        last_payload = payload
        if payload.get("status") in {"completed", "needs_review", "low_confidence", "failed"}:
            return payload
        time.sleep(poll_interval_seconds)

    pytest.fail(f"Job {job_id} did not reach a terminal state. Last payload: {last_payload}")
