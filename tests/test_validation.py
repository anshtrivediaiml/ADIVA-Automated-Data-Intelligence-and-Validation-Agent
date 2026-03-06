"""
ADIVA — Validation API Test

Tests the new /api/validate/* endpoints end-to-end.
Run with: python tests/test_validation.py

Requires the API to be running:
    uvicorn api.main:app --reload --app-dir backend

Uses credentials from environment or defaults (ansh@adiva.ai / adiva@admin).
"""

import json
import os
import sys
import requests
from pathlib import Path

BASE_URL = "http://localhost:8000"

# Credentials — match what's in your Supabase/auth setup
EMAIL    = os.getenv("TEST_EMAIL", "ansh@adiva.ai")
PASSWORD = os.getenv("TEST_PASSWORD", "your_new_password")


def get_token() -> str:
    """Login and return JWT access token."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=10,
    )
    if resp.status_code != 200:
        print(f"✗ Login failed ({resp.status_code}): {resp.text}")
        sys.exit(1)
    token = resp.json().get("access_token")
    print(f"✓ Logged in as {EMAIL}")
    return token


def get_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_validate_extraction(token: str, extraction_id: str):
    """POST /api/validate/{extraction_id}"""
    print(f"\n{'='*60}")
    print(f"Testing POST /api/validate/{extraction_id}")
    print("="*60)

    resp = requests.post(
        f"{BASE_URL}/api/validate/{extraction_id}",
        headers=get_headers(token),
        timeout=120,
    )
    print(f"Status: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        print(f"  is_valid:         {data['is_valid']}")
        print(f"  confidence_score: {data['confidence_score']}")
        print(f"  document_type:    {data.get('document_type')}")
        print(f"  errors:           {sum(1 for e in data['error_log'] if e['severity'] == 'error')}")
        print(f"  warnings:         {sum(1 for e in data['error_log'] if e['severity'] == 'warning')}")
        print(f"  truth_tests:      {len(data.get('truth_tests', []))}")
        print(f"  norm_changes:     {len(data.get('normalisation_changes', []))}")
        print(f"  time:             {data.get('validation_time_seconds')}s")

        # Basic assertions
        assert isinstance(data["is_valid"], bool), "is_valid must be bool"
        assert 0.0 <= data["confidence_score"] <= 1.0, "confidence_score must be 0-1"
        assert isinstance(data["error_log"], list), "error_log must be list"
        print("✓ validate_extraction PASSED")
        return data
    else:
        print(f"✗ FAILED: {resp.text}")
        return None


def test_validate_without_token(extraction_id: str):
    """Without JWT → must get 401."""
    print(f"\n{'='*60}")
    print("Testing unauthenticated request (expect 401)")
    print("="*60)
    resp = requests.post(
        f"{BASE_URL}/api/validate/{extraction_id}",
        timeout=10,
    )
    print(f"Status: {resp.status_code}")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
    print("✓ Unauthenticated request correctly rejected (401)")


def test_list_reports(token: str):
    """GET /api/validate/reports"""
    print(f"\n{'='*60}")
    print("Testing GET /api/validate/reports")
    print("="*60)
    resp = requests.get(
        f"{BASE_URL}/api/validate/reports",
        headers=get_headers(token),
        timeout=10,
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Total reports: {data['total']}")
        for r in data["reports"][:3]:
            print(f"  - {r['filename']} | valid={r['is_valid']} | conf={r['confidence_score']}")
        print("✓ list_reports PASSED")
    else:
        print(f"✗ FAILED: {resp.text}")


def test_validate_unknown_extraction(token: str):
    """Validate a non-existent extraction → should return a report with is_valid=False"""
    print(f"\n{'='*60}")
    print("Testing non-existent extraction_id (expect 200 + is_valid=False)")
    print("="*60)
    resp = requests.post(
        f"{BASE_URL}/api/validate/THIS_DOES_NOT_EXIST_12345",
        headers=get_headers(token),
        timeout=10,
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        assert data["is_valid"] == False
        print(f"✓ Non-existent extraction correctly returned is_valid=False")
    else:
        print(f"  (returned {resp.status_code} — also acceptable)")


def find_extraction_id() -> str:
    """Find the most recently created extraction folder to use in tests."""
    extracted_dir = Path(__file__).parent.parent / "outputs" / "extracted"
    if not extracted_dir.exists():
        return None
    folders = sorted(
        [f for f in extracted_dir.iterdir() if f.is_dir() and (f / "extraction.json").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return folders[0].name if folders else None


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ADIVA — Validation API Test Suite")
    print("="*60)

    # Get JWT token
    token = get_token()

    # Find a real extraction to test with
    extraction_id = find_extraction_id()
    if not extraction_id:
        print("\n⚠ No extraction found in outputs/extracted/. Skipping live test.")
        print("  Run an extraction first, then re-run this test.")
    else:
        print(f"\nUsing extraction: {extraction_id}")

        # Core tests
        test_validate_without_token(extraction_id)
        report = test_validate_extraction(token, extraction_id)
        test_list_reports(token)

    # Always test the not-found case
    test_validate_unknown_extraction(token)

    print("\n" + "="*60)
    print("✓ All validation tests complete!")
    print("="*60)
