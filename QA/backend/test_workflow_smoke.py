from __future__ import annotations

import os

import pytest
import httpx

from helpers import poll_job_until_terminal


@pytest.mark.integration
def test_single_upload_job_result_review_flow(
    http_client: httpx.Client,
    api_base_url: str,
    auth_headers: dict[str, str],
    sample_file_path,
    qa_timeout_seconds: int,
    qa_poll_interval_seconds: int,
) -> None:
    if os.getenv("QA_ENABLE_UPLOAD_FLOW", "0") != "1":
        pytest.skip("Set QA_ENABLE_UPLOAD_FLOW=1 to run upload/result/review integration flow.")

    with sample_file_path.open("rb") as handle:
        upload_response = http_client.post(
            f"{api_base_url}/extract",
            headers=auth_headers,
            files={"file": (sample_file_path.name, handle, "application/octet-stream")},
        )

    assert upload_response.status_code == 202, upload_response.text
    upload_payload = upload_response.json()
    job_id = upload_payload["job_id"]

    job_payload = poll_job_until_terminal(
        client=http_client,
        api_base_url=api_base_url,
        auth_headers=auth_headers,
        job_id=job_id,
        timeout_seconds=qa_timeout_seconds,
        poll_interval_seconds=qa_poll_interval_seconds,
    )
    assert job_payload["status"] in {"completed", "needs_review", "low_confidence", "failed"}

    result_response = http_client.get(f"{api_base_url}/results/{job_id}", headers=auth_headers)
    assert result_response.status_code in {200, 409}, result_response.text
    if result_response.status_code == 200:
        result_payload = result_response.json()
        assert result_payload["job_id"] == job_id
        assert "artifacts" in result_payload

        review_case_id = result_payload.get("review_case_id")
        if review_case_id:
            review_response = http_client.get(
                f"{api_base_url}/reviews/{review_case_id}",
                headers=auth_headers,
            )
            assert review_response.status_code == 200, review_response.text
            review_payload = review_response.json()
            assert review_payload["review_id"] == review_case_id
