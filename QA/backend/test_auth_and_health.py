from __future__ import annotations

import httpx
import pytest


@pytest.mark.smoke
def test_health_endpoint(http_client: httpx.Client, api_base_url: str) -> None:
    response = http_client.get(f"{api_base_url}/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"healthy", "degraded", "down"}


@pytest.mark.smoke
def test_status_endpoint(http_client: httpx.Client, api_base_url: str) -> None:
    response = http_client.get(f"{api_base_url}/status")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)


@pytest.mark.smoke
def test_login_and_me(
    http_client: httpx.Client,
    api_base_url: str,
    qa_credentials: dict[str, str],
    auth_headers: dict[str, str],
) -> None:
    login_response = http_client.post(f"{api_base_url}/auth/login", json=qa_credentials)
    assert login_response.status_code == 200, login_response.text
    login_payload = login_response.json()
    assert login_payload["token_type"] == "bearer"
    assert login_payload["user"]["email"] == qa_credentials["email"]

    me_response = http_client.get(f"{api_base_url}/auth/me", headers=auth_headers)
    assert me_response.status_code == 200, me_response.text
    me_payload = me_response.json()
    assert me_payload["email"] == qa_credentials["email"]


@pytest.mark.smoke
def test_refresh_token(
    http_client: httpx.Client,
    api_base_url: str,
    auth_tokens: dict[str, str],
) -> None:
    response = http_client.post(
        f"{api_base_url}/auth/refresh",
        json={"refresh_token": auth_tokens["refresh_token"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
