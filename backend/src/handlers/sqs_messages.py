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
