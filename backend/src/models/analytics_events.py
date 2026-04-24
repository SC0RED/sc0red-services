"""Analytics event models for the sc0red CTA banner funnel.

Two models:
- `AnalyticsEvent`: the envelope a client posts to `POST /analytics/events`.
  Fields are client-controlled.
- `EnrichedAnalyticsEvent`: the shape written to CloudWatch Logs. Adds
  `user_id` and `org_id`, which the backend derives from the authenticated
  JWT and MUST NOT accept from the request body.

See `openspec/changes/opportunities-cta-analytics/design.md` for the full
design rationale (sink, privacy posture, schema versioning).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

AnalyticsEventType = Literal[
    "sc0red_cta_banner_expanded",
    "sc0red_cta_banner_collapsed",
    "sc0red_cta_clicked",
    "sc0red_cta_rendered_in_pdf",
]

AnalyticsSource = Literal["web", "pdf"]

ActiveLeverFilter = Literal["Revenue Side", "Cost Side"]

ANALYTICS_VERSION = "1"


class AnalyticsEvent(BaseModel):
    """Client-submitted envelope for a CTA analytics event.

    The backend ignores any `user_id` / `org_id` fields if a client attempts
    to send them — those are enriched from the authenticated JWT at handler
    time (see `EnrichedAnalyticsEvent`). Rejecting unknown fields rather than
    silently dropping them surfaces client bugs early.
    """

    model_config = {"extra": "forbid"}

    event_id: str = Field(min_length=1)
    event_type: AnalyticsEventType
    timestamp: str = Field(min_length=1)
    analytics_version: Literal["1"] = ANALYTICS_VERSION
    source: AnalyticsSource
    analysis_id: str = Field(min_length=1)
    # `opportunity_count` is "how many opportunities the user actually saw"
    # at emit time, i.e. the post-filter count on web and the full count in
    # the PDF (which renders all). Funnel queries comparing web vs. PDF on
    # this field should account for that surface-dependent baseline.
    opportunity_count: int = Field(ge=0)
    active_lever_filter: ActiveLeverFilter | None = None

    @model_validator(mode="after")
    def _validate_pdf_rendered_event(self) -> AnalyticsEvent:
        """PDF-render events MUST carry source='pdf' and MUST NOT carry a lever filter.

        The PDF surface does not support per-lever filtering, so an
        `active_lever_filter` on a PDF event is a client bug that would
        corrupt funnel queries later.
        """
        if self.event_type == "sc0red_cta_rendered_in_pdf":
            if self.source != "pdf":
                raise ValueError("sc0red_cta_rendered_in_pdf requires source='pdf'")
            if self.active_lever_filter is not None:
                raise ValueError("sc0red_cta_rendered_in_pdf must not carry active_lever_filter")
        elif self.source != "web":
            # All web-origin events must declare source='web' — prevents a
            # misrouted PDF emit from being miscategorized as web.
            raise ValueError(f"{self.event_type} requires source='web'")
        return self


class EnrichedAnalyticsEvent(BaseModel):
    """Event shape written to CloudWatch Logs.

    Composes `AnalyticsEvent` with server-enriched identity fields. Built
    by the handler after validating the client envelope and pulling
    identity from the authenticated context.
    """

    model_config = {"extra": "forbid"}

    event_id: str
    event_type: AnalyticsEventType
    timestamp: str
    analytics_version: Literal["1"]
    source: AnalyticsSource
    analysis_id: str
    opportunity_count: int
    active_lever_filter: ActiveLeverFilter | None
    user_id: str = Field(min_length=1)
    org_id: str = Field(min_length=1)

    @classmethod
    def from_client_event(
        cls,
        client_event: AnalyticsEvent,
        *,
        user_id: str,
        org_id: str,
    ) -> EnrichedAnalyticsEvent:
        """Build an enriched event from a validated client envelope + auth context."""
        return cls(
            event_id=client_event.event_id,
            event_type=client_event.event_type,
            timestamp=client_event.timestamp,
            analytics_version=client_event.analytics_version,
            source=client_event.source,
            analysis_id=client_event.analysis_id,
            opportunity_count=client_event.opportunity_count,
            active_lever_filter=client_event.active_lever_filter,
            user_id=user_id,
            org_id=org_id,
        )
