"""Typed SQS message builders — single source of truth for message schema."""

from __future__ import annotations

import json


def build_analysis_message(
    *,
    url: str,
    org_id: str,
    user_id: str,
    scan_id: str,
    request_id: str,
    company_name: str = "",
) -> str:
    """Build a JSON message for a new company analysis."""
    return json.dumps(
        {
            "url": url,
            "org_id": org_id,
            "user_id": user_id,
            "scan_id": scan_id,
            "company_name": company_name,
            "request_id": request_id,
        }
    )


def build_portfolio_discovery_message(
    *,
    url: str,
    org_id: str,
    user_id: str,
    scan_id: str,
) -> str:
    """Build a JSON message to dispatch portfolio discovery to the SQS worker.

    The worker runs the ``DiscoverPortfolio`` → ``ValidatePortfolioCompanies``
    pipeline asynchronously so the API handler never blocks on AI calls.
    """
    return json.dumps(
        {
            "type": "portfolio_discovery",
            "url": url,
            "org_id": org_id,
            "user_id": user_id,
            "scan_id": scan_id,
        }
    )


def build_reanalysis_message(
    *,
    analysis_id: str,
    url: str,
    org_id: str,
    user_id: str,
    scan_id: str,
) -> str:
    """Build a JSON message for re-analyzing an existing company."""
    return json.dumps(
        {
            "reanalyze": True,
            "analysis_id": analysis_id,
            "url": url,
            "org_id": org_id,
            "user_id": user_id,
            "scan_id": scan_id,
            "request_id": analysis_id,
        }
    )


def build_strategy_map_message(
    *,
    analysis_id: str,
    scan_id: str,
) -> str:
    """Build a JSON message for the on-demand strategy-map worker.

    Per the strategy-map-on-demand spec, the message lands on the dedicated
    `janus-strategy-map-queue`. The worker loads the latest assessment for
    ``analysis_id``, runs the strategy-map generation, persists the result,
    and pushes an AppSync ``strategy_map_complete`` event.

    The message intentionally carries only ``analysis_id`` + ``scan_id``;
    ``org_id`` and ``user_id`` are loaded from the persisted company record
    by the hydration layer rather than threaded through the message. This
    keeps the message contract honest about what the consumer reads.
    """
    return json.dumps(
        {
            "type": "strategy_map_generation",
            "analysis_id": analysis_id,
            "scan_id": scan_id,
        }
    )
