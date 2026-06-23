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


def build_portfolio_deepen_message(
    *,
    url: str,
    org_id: str,
    user_id: str,
    scan_id: str,
) -> str:
    """Build a JSON message to dispatch a customer-triggered deepen to the worker.

    The worker reads the scan's current companies as the seed, runs the
    ``DeepenPortfolio`` → ``ValidatePortfolioCompanies`` pipeline, and merges the
    newly-recovered companies back into the awaiting-confirmation list.
    """
    return json.dumps(
        {
            "type": "portfolio_deepen",
            "url": url,
            "org_id": org_id,
            "user_id": user_id,
            "scan_id": scan_id,
        }
    )


def build_portfolio_source_url_message(
    *,
    source_url: str,
    org_id: str,
    user_id: str,
    scan_id: str,
) -> str:
    """Build a JSON message to dispatch a customer-provided source URL.

    ``source_url`` is the page the customer says lists the portfolio. The worker
    seeds from the scan's current companies, scrapes that page server-side via
    ``FetchProvidedSource`` → ``ValidatePortfolioCompanies``, and merges the
    newly-found companies back into the awaiting-confirmation list.
    """
    return json.dumps(
        {
            "type": "portfolio_source_url",
            "source_url": source_url,
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
