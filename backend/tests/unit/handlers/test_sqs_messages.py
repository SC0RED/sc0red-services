"""Tests for typed SQS message builders."""

from __future__ import annotations

import json

from src.handlers.sqs_messages import (
    build_analysis_message,
    build_portfolio_discovery_message,
    build_reanalysis_message,
    build_strategy_map_message,
)


class TestBuildAnalysisMessage:
    def test_produces_valid_json_with_all_fields(self) -> None:
        payload = build_analysis_message(
            url="https://acme.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
            request_id="req-1",
            company_name="Acme Corp",
        )
        data = json.loads(payload)
        assert data == {
            "url": "https://acme.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "company_name": "Acme Corp",
            "request_id": "req-1",
        }

    def test_company_name_defaults_to_empty(self) -> None:
        payload = build_analysis_message(
            url="https://acme.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
            request_id="req-1",
        )
        assert json.loads(payload)["company_name"] == ""


class TestBuildReanalysisMessage:
    def test_sets_reanalyze_flag_and_all_fields(self) -> None:
        payload = build_reanalysis_message(
            analysis_id="ana-1",
            url="https://acme.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
        )
        data = json.loads(payload)
        assert data == {
            "reanalyze": True,
            "analysis_id": "ana-1",
            "url": "https://acme.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
            "request_id": "ana-1",
        }


class TestBuildPortfolioDiscoveryMessage:
    def test_sets_portfolio_discovery_type(self) -> None:
        payload = build_portfolio_discovery_message(
            url="https://perotjain.com",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
        )
        data = json.loads(payload)
        assert data == {
            "type": "portfolio_discovery",
            "url": "https://perotjain.com",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
        }

    def test_payload_is_valid_json(self) -> None:
        payload = build_portfolio_discovery_message(
            url="https://pefirm.com",
            org_id="org-2",
            user_id="user-2",
            scan_id="scan-2",
        )
        # Round-trip through JSON to confirm no non-serializable values
        assert json.loads(payload)["type"] == "portfolio_discovery"


class TestBuildStrategyMapMessage:
    """Per the strategy-map-on-demand spec, the on-demand worker consumes
    messages on the dedicated `janus-strategy-map-queue` discriminated by
    ``type == "strategy_map_generation"``. The payload carries the analysis
    identifiers needed to reload assessment data + push AppSync events."""

    def test_sets_strategy_map_generation_type(self) -> None:
        payload = build_strategy_map_message(
            analysis_id="ana-7",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-1",
        )
        data = json.loads(payload)
        assert data == {
            "type": "strategy_map_generation",
            "analysis_id": "ana-7",
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": "scan-1",
        }

    def test_payload_is_valid_json(self) -> None:
        payload = build_strategy_map_message(
            analysis_id="ana-9",
            org_id="org-9",
            user_id="user-9",
            scan_id="scan-9",
        )
        # Round-trip — fails fast if any value isn't JSON-serializable.
        assert json.loads(payload)["analysis_id"] == "ana-9"
