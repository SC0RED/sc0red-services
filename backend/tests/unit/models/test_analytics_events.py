"""Tests for the analytics event envelope and enriched event model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.analytics_events import (
    ANALYTICS_VERSION,
    AnalyticsEvent,
    EnrichedAnalyticsEvent,
)


def _web_event(**overrides: object) -> dict[str, object]:
    """Build a default web-source analytics event payload.

    The default ``event_type`` is the strategy-map CTA "rendered" event
    — the only web-source CTA emitter that survives Phase 5 of
    ``redesign-strategy-map`` (the opportunities-list ``Sc0redCTABanner``
    and its three event types — ``_banner_expanded`` /
    ``_banner_collapsed`` / ``_clicked`` — were removed). Strategy-map
    events MUST carry ``active_lever_filter=None``; the validator
    rejects non-null lever filters for these event types.
    """
    base: dict[str, object] = {
        "event_id": "uuid-1",
        "event_type": "sc0red_cta_rendered_strategy_map",
        "timestamp": "2026-04-24T12:00:00.000Z",
        "analytics_version": "1",
        "source": "web",
        "analysis_id": "assess-1",
        "opportunity_count": 3,
        "active_lever_filter": None,
    }
    base.update(overrides)
    return base


def _pdf_event(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "event_id": "uuid-2",
        "event_type": "sc0red_cta_rendered_in_pdf",
        "timestamp": "2026-04-24T12:00:00.000Z",
        "analytics_version": "1",
        "source": "pdf",
        "analysis_id": "assess-1",
        "opportunity_count": 3,
        "active_lever_filter": None,
    }
    base.update(overrides)
    return base


class TestAnalyticsEventStrategyMapEvents:
    """Strategy-map CTA event types — web-source, no lever filter.

    These events back the conversion funnel for the Vector Advisory
    strategy-map product (see PR #239 review feedback). Surface
    invariants: source='web', `active_lever_filter` MUST be null.
    """

    def test_rendered_strategy_map_event_parses(self) -> None:
        event = AnalyticsEvent(
            **_web_event(
                event_type="sc0red_cta_rendered_strategy_map",
                opportunity_count=0,
                active_lever_filter=None,
            )
        )
        assert event.event_type == "sc0red_cta_rendered_strategy_map"
        assert event.source == "web"
        assert event.active_lever_filter is None

    def test_clicked_strategy_map_event_parses(self) -> None:
        event = AnalyticsEvent(
            **_web_event(
                event_type="sc0red_cta_clicked_strategy_map",
                opportunity_count=0,
                active_lever_filter=None,
            )
        )
        assert event.event_type == "sc0red_cta_clicked_strategy_map"

    def test_strategy_map_event_with_lever_filter_rejected(self) -> None:
        # The strategy-map surface has no lever-filter concept; a
        # non-null filter would corrupt funnel queries that join across
        # surfaces on event_type.
        with pytest.raises(ValidationError, match="must not carry active_lever_filter"):
            AnalyticsEvent(
                **_web_event(
                    event_type="sc0red_cta_rendered_strategy_map",
                    active_lever_filter="Revenue Side",
                )
            )

    def test_strategy_map_event_with_pdf_source_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires source='web'"):
            AnalyticsEvent(
                **_web_event(
                    event_type="sc0red_cta_clicked_strategy_map",
                    source="pdf",
                    active_lever_filter=None,
                )
            )


class TestAnalyticsEventPdfEvent:
    def test_pdf_render_event_parses(self) -> None:
        event = AnalyticsEvent(**_pdf_event())
        assert event.event_type == "sc0red_cta_rendered_in_pdf"
        assert event.source == "pdf"
        assert event.active_lever_filter is None

    def test_pdf_event_with_web_source_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires source='pdf'"):
            AnalyticsEvent(**_pdf_event(source="web"))

    def test_pdf_event_with_lever_filter_rejected(self) -> None:
        with pytest.raises(ValidationError, match="must not carry active_lever_filter"):
            AnalyticsEvent(**_pdf_event(active_lever_filter="Revenue Side"))

    def test_web_event_with_pdf_source_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires source='web'"):
            AnalyticsEvent(**_web_event(source="pdf"))


class TestAnalyticsEventValidation:
    def test_unknown_event_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsEvent(**_web_event(event_type="sc0red_cta_unicorn"))

    def test_empty_event_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsEvent(**_web_event(event_id=""))

    def test_empty_analysis_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsEvent(**_web_event(analysis_id=""))

    def test_empty_timestamp_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsEvent(**_web_event(timestamp=""))

    def test_negative_opportunity_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsEvent(**_web_event(opportunity_count=-1))

    def test_zero_opportunity_count_allowed(self) -> None:
        # Zero is a legitimate count when filters exclude everything.
        event = AnalyticsEvent(**_web_event(opportunity_count=0))
        assert event.opportunity_count == 0

    def test_wrong_analytics_version_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsEvent(**_web_event(analytics_version="2"))

    def test_extra_fields_rejected(self) -> None:
        # Anti-spoofing: a client including user_id / org_id in the body is
        # a bug or an attempted spoof. Either way — reject loudly.
        with pytest.raises(ValidationError):
            AnalyticsEvent(**_web_event(user_id="spoofed-user"))
        with pytest.raises(ValidationError):
            AnalyticsEvent(**_web_event(org_id="spoofed-org"))


class TestEnrichedAnalyticsEvent:
    def test_from_client_event_adds_identity(self) -> None:
        client = AnalyticsEvent(**_web_event())
        enriched = EnrichedAnalyticsEvent.from_client_event(
            client, user_id="user-1", org_id="org-1"
        )
        assert enriched.user_id == "user-1"
        assert enriched.org_id == "org-1"
        assert enriched.event_id == client.event_id
        assert enriched.analysis_id == client.analysis_id

    def test_empty_user_id_rejected(self) -> None:
        client = AnalyticsEvent(**_web_event())
        with pytest.raises(ValidationError):
            EnrichedAnalyticsEvent.from_client_event(client, user_id="", org_id="org-1")

    def test_empty_org_id_rejected(self) -> None:
        client = AnalyticsEvent(**_web_event())
        with pytest.raises(ValidationError):
            EnrichedAnalyticsEvent.from_client_event(client, user_id="user-1", org_id="")

    def test_round_trip_preserves_all_fields(self) -> None:
        client = AnalyticsEvent(**_web_event())
        enriched = EnrichedAnalyticsEvent.from_client_event(
            client, user_id="user-1", org_id="org-1"
        )
        dumped = enriched.model_dump()
        assert dumped["event_id"] == "uuid-1"
        assert dumped["event_type"] == "sc0red_cta_rendered_strategy_map"
        assert dumped["user_id"] == "user-1"
        assert dumped["org_id"] == "org-1"
        assert dumped["analytics_version"] == ANALYTICS_VERSION
