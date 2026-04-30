"""Tests for the internal-key authenticated endpoints.

Covers the `INTERNAL_API_KEY` env-var contract (missing → 500), the
constant-time key comparison (wrong key → 401), the `X-Org-Id` requirement,
the org-scoped 404 (cross-org reads return 404, never reveal existence),
and the happy path that returns the same payload as the user-facing
`GET /api/analysis/{id}` endpoint.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.handlers.internal_handlers import (
    INTERNAL_API_KEY_ENVIRONMENT_NAME,
    handle_internal_get_analysis,
)


VALID_KEY = "internal-key-32-bytes-of-randomness-please"


def _event(*, headers: dict[str, str] | None = None) -> dict[str, Any]:
    return {"headers": headers or {}}


def _make_storage(
    *,
    company: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> MagicMock:
    storage = MagicMock()
    company_repo = MagicMock()
    company_repo.get_by_id.return_value = company
    storage.create_company_repository.return_value = company_repo

    if company is not None and payload is not None:
        # build_analysis_payload reads scan_repo + assessment_repo. Stub to
        # return empty so the handler-side composition runs cleanly.
        scan_repo = MagicMock()
        scan_repo.get_by_id.return_value = None
        storage.create_scan_repository.return_value = scan_repo
        assessment_repo = MagicMock()
        assessment_repo.find_by_company.return_value = []
        storage.create_assessment_repository.return_value = assessment_repo
    return storage


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts with the env var unset; tests that need it set
    should call `monkeypatch.setenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, ...)`."""
    monkeypatch.delenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, raising=False)


def test_returns_500_when_internal_key_env_missing() -> None:
    storage = _make_storage()
    response = handle_internal_get_analysis(_event(), storage, "a-1")
    assert response["statusCode"] == 500


def test_returns_401_when_provided_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, VALID_KEY)
    storage = _make_storage()
    response = handle_internal_get_analysis(_event(), storage, "a-1")
    assert response["statusCode"] == 401


def test_returns_401_when_provided_key_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, VALID_KEY)
    storage = _make_storage()
    response = handle_internal_get_analysis(
        _event(headers={"X-Internal-Api-Key": "wrong-key", "X-Org-Id": "org-1"}),
        storage,
        "a-1",
    )
    assert response["statusCode"] == 401


def test_returns_400_when_org_id_header_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, VALID_KEY)
    storage = _make_storage()
    response = handle_internal_get_analysis(
        _event(headers={"X-Internal-Api-Key": VALID_KEY}),
        storage,
        "a-1",
    )
    assert response["statusCode"] == 400


def test_returns_404_when_company_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, VALID_KEY)
    storage = _make_storage(company=None)
    response = handle_internal_get_analysis(
        _event(headers={"X-Internal-Api-Key": VALID_KEY, "X-Org-Id": "org-1"}),
        storage,
        "a-1",
    )
    assert response["statusCode"] == 404


def test_returns_404_when_company_in_other_org(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cross-org reads return 404 — never reveal existence of cross-org records."""
    monkeypatch.setenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, VALID_KEY)
    storage = _make_storage(company={"id": "a-1", "org_id": "org-OTHER"})
    response = handle_internal_get_analysis(
        _event(headers={"X-Internal-Api-Key": VALID_KEY, "X-Org-Id": "org-1"}),
        storage,
        "a-1",
    )
    assert response["statusCode"] == 404


def test_happy_path_returns_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, VALID_KEY)
    company = {
        "id": "a-1",
        "org_id": "org-1",
        "company_name": "Acme",
        "company_url": "https://acme.example",
        "industry": "Software",
        "overall_risk_score": 7.5,
        "risk_tier": "high",
    }
    storage = _make_storage(company=company, payload=company)
    response = handle_internal_get_analysis(
        _event(headers={"X-Internal-Api-Key": VALID_KEY, "X-Org-Id": "org-1"}),
        storage,
        "a-1",
    )
    assert response["statusCode"] == 200
    import json

    body = json.loads(response["body"])
    assert body["companyName"] == "Acme"
    assert body["riskTier"] == "high"


def test_lowercase_header_names_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """API Gateway sometimes lowercases header names; case-insensitive lookup."""
    monkeypatch.setenv(INTERNAL_API_KEY_ENVIRONMENT_NAME, VALID_KEY)
    company = {"id": "a-1", "org_id": "org-1", "company_name": "Acme"}
    storage = _make_storage(company=company, payload=company)
    response = handle_internal_get_analysis(
        _event(headers={"x-internal-api-key": VALID_KEY, "x-org-id": "org-1"}),
        storage,
        "a-1",
    )
    assert response["statusCode"] == 200
