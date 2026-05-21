"""Analytics event models for the sc0red CTA funnel (strategy-map + PDF surfaces).

Two models:
- `AnalyticsEvent`: the envelope a client posts to `POST /analytics/events`.
  Fields are client-controlled.
- `EnrichedAnalyticsEvent`: the shape written to CloudWatch Logs. Adds
  `user_id` and `org_id`, which the backend derives from the authenticated
  JWT and MUST NOT accept from the request body.

The three opportunities-list banner events
(``sc0red_cta_banner_expanded``, ``_collapsed``, ``sc0red_cta_clicked``)
that this funnel originally tracked were removed end-to-end under
``redesign-strategy-map`` Phase 5 when the standalone
``Sc0redCTABanner`` was deleted from the analysis page. The surviving
event types track the strategy-map deep-dive CTA (web) and the PDF
render variant.

See `openspec/changes/opportunities-cta-analytics/design.md` for the
original sink / privacy posture / schema versioning design rationale.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

AnalyticsEventType = Literal[
    # ``_rendered_in_pdf`` is emitted by the PDF renderer when the
    # strategy-map deep-dive CTA appears on the printable export.
    "sc0red_cta_rendered_in_pdf",
    # Strategy-map deep-dive CTA — the variant rendered DIRECTLY under
    # the strategy-map table (mid-page placement). ``_rendered`` fires
    # on component mount (the CTA is always-visible when the strategy
    # map is present); ``_clicked`` fires on the contact-link click.
    "sc0red_cta_rendered_strategy_map",
    "sc0red_cta_clicked_strategy_map",
    # End-of-analysis deep-dive CTA — the variant rendered at the
    # BOTTOM of the analysis page, after every other section. Same
    # component (``DeepDiveCTA``) as the strategy-map placement but
    # the analytics event name MUST differ so the funnel can attribute
    # impressions and clicks to the correct surface. Without distinct
    # names, the bottom CTA's impressions double-count the strategy-
    # map funnel — the bug Phase 11 of redesign-analysis-visuals
    # fixes (see ``analysis-detail-narrative`` spec requirement
    # "DeepDiveCTA distinguishes placement in analytics").
    "sc0red_cta_rendered_analysis_end",
    "sc0red_cta_clicked_analysis_end",
]

# Internal-only set of CTA event types that share the strategy-map
# surface invariants (web-source + no lever filter). Kept beside the
# Literal so the validator can branch on them without restating the
# names. The analysis-end CTA shares the same invariants because it's
# the same component in a different placement — no lever-filter
# concept either, still web-source.
_DEEP_DIVE_CTA_EVENT_TYPES = frozenset(
    {
        "sc0red_cta_rendered_strategy_map",
        "sc0red_cta_clicked_strategy_map",
        "sc0red_cta_rendered_analysis_end",
        "sc0red_cta_clicked_analysis_end",
    }
)

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
    def _validate_event_surface_invariants(self) -> AnalyticsEvent:
        """Each event type has surface-specific invariants — enforce them here.

        - PDF-render: must carry source='pdf' and MUST NOT carry a lever
          filter. The PDF surface does not support per-lever filtering.
        - Strategy-map (rendered/clicked): must carry source='web' and
          MUST NOT carry a lever filter. The strategy-map surface has
          no lever-filter concept; a non-null filter would corrupt
          funnel queries that join across surfaces on event_type.
        - All other events: must carry source='web'.

        Surface-specific invariants live here (not in handler code) so
        a malformed envelope is rejected at the model boundary, before
        it can be persisted to CloudWatch and contaminate funnel data.
        """
        if self.event_type == "sc0red_cta_rendered_in_pdf":
            if self.source != "pdf":
                raise ValueError("sc0red_cta_rendered_in_pdf requires source='pdf'")
            if self.active_lever_filter is not None:
                raise ValueError("sc0red_cta_rendered_in_pdf must not carry active_lever_filter")
            return self

        # All non-PDF events must declare source='web' — prevents a
        # misrouted PDF emit from being miscategorized as web.
        if self.source != "web":
            raise ValueError(f"{self.event_type} requires source='web'")

        if self.event_type in _DEEP_DIVE_CTA_EVENT_TYPES and self.active_lever_filter is not None:
            raise ValueError(f"{self.event_type} must not carry active_lever_filter")

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
