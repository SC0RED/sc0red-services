"""Event model for sc0red Services pipeline requests.

Mirrors the engine's event model pattern for pipeline invocations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Sc0redServicesEvent(BaseModel):
    """Event payload that triggers a sc0red Services pipeline execution."""

    request_id: str = ""
    request_type: str = ""  # company_analysis | portfolio_scan
    url: str = ""
    tenant_id: str = ""
    org_id: str = ""
    user_id: str = ""
    scan_id: str = ""
    company_name: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)
