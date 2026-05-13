"""Tests for the strategyMap field on the analysis-payload response.

Verifies that `build_analysis_payload`:
  - Includes a `strategyMap` field when the assessment has one
    persisted, with the camelCase shape the frontend expects.
  - Returns `strategyMap: None` when no strategy map is persisted
    (legacy analyses).

This guards the contract between `assessment_repo.get_strategy_map`
and the API surface — the frontend's conditional render
(`{data.strategyMap ? <StrategyMapView .../> : null}`) depends on
this field being absent / null for legacy analyses and populated
with a complete StrategyMap for newly-analysed companies.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.handlers.analysis_payload import build_analysis_payload


def _make_storage(strategy_map: dict[str, Any] | None) -> MagicMock:
    """Build a storage stub that returns the given strategy map for the assessment."""
    storage = MagicMock()

    scan_repo = MagicMock()
    scan_repo.get_by_id.return_value = None
    storage.create_scan_repository.return_value = scan_repo

    assessment_repo = MagicMock()
    assessment_repo.find_by_company.return_value = [
        {"id": "assess-1", "created_at": "2026-01-01T00:00:00Z"},
    ]
    assessment_repo.get_risk_scores.return_value = []
    assessment_repo.get_opportunities.return_value = []
    assessment_repo.get_ebitda_tree.return_value = None
    assessment_repo.get_value_chain.return_value = None
    assessment_repo.get_strategy_map.return_value = strategy_map
    assessment_repo.get_documents.return_value = []
    storage.create_assessment_repository.return_value = assessment_repo

    return storage


_FULL_STRATEGY_MAP: dict[str, Any] = {
    "vision": {"statement": "v", "synthesised": False, "rationale": "r"},
    "mission": {"statement": "m", "synthesised": False, "rationale": "r"},
    "valueProposition": {
        "primary": "customer_intimacy",
        "secondary": None,
        "rationale": "r",
    },
    "strategicPriorities": [
        {"name": "P1", "result": "r1"},
        {"name": "P2", "result": "r2"},
    ],
    "financial": {"objectives": []},
    "customer": {"objectives": []},
    "internalProcesses": {"themes": []},
    "organizationalCapacity": {
        "people": {"id": "O.P", "title": "t", "definition": "d", "confidence": "HIGH"},
        "technology": {"id": "O.T", "title": "t", "definition": "d", "confidence": "HIGH"},
        "culture": {"id": "O.C", "title": "t", "definition": "d", "confidence": "LOW"},
    },
    "arrows": [],
    "whatsMissing": [],
    "coreValues": {"values": ["a", "b", "c"], "synthesised": False, "rationale": "r"},
}


def test_payload_includes_strategy_map_when_persisted() -> None:
    """When the assessment has a strategy map, build_analysis_payload returns it."""
    storage = _make_storage(strategy_map=_FULL_STRATEGY_MAP)
    company = {"id": "c-1", "company_name": "Test Corp", "company_url": "https://test.example"}

    payload = build_analysis_payload(storage, company, analysis_id="c-1")

    assert "strategyMap" in payload
    assert payload["strategyMap"] is not None
    assert payload["strategyMap"]["valueProposition"]["primary"] == "customer_intimacy"
    # The persisted shape passes through unchanged — no double-conversion.
    assert payload["strategyMap"] == _FULL_STRATEGY_MAP


def test_payload_strategy_map_is_none_for_legacy_analyses() -> None:
    """When the assessment has no strategy map, the field is None (not missing)."""
    storage = _make_storage(strategy_map=None)
    company = {"id": "c-1", "company_name": "Test Corp"}

    payload = build_analysis_payload(storage, company, analysis_id="c-1")

    assert "strategyMap" in payload
    assert payload["strategyMap"] is None


def test_payload_with_no_assessments_omits_strategy_map_lookup() -> None:
    """When no assessments exist, strategyMap is None and the repo is not queried."""
    storage = MagicMock()
    storage.create_scan_repository.return_value.get_by_id.return_value = None
    assessment_repo = MagicMock()
    assessment_repo.find_by_company.return_value = []
    storage.create_assessment_repository.return_value = assessment_repo

    company = {"id": "c-1", "company_name": "Test Corp"}
    payload = build_analysis_payload(storage, company, analysis_id="c-1")

    assert payload["strategyMap"] is None
    assessment_repo.get_strategy_map.assert_not_called()


def test_payload_omits_generation_state_field() -> None:
    """Per ``redesign-strategy-map`` Phase 4 the on-demand worker is
    gone — the analysis payload no longer carries a
    ``strategyMapGenerationState`` field (the strategy map is either
    present, from the inline pipeline, or absent for legacy analyses
    that pre-date the inline integration).
    """
    storage = _make_storage(strategy_map=None)
    company = {
        "id": "c-1",
        "company_name": "Test Corp",
        # Legacy persisted records may still carry this attribute; the
        # payload builder MUST NOT propagate it to the frontend.
        "strategy_map_generation_state": "generating",
    }

    payload = build_analysis_payload(storage, company, analysis_id="c-1")

    assert "strategyMapGenerationState" not in payload
