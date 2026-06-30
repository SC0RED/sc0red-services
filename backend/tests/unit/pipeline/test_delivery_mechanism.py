"""Tests for the delivery-mechanism classifier."""

from src.pipeline.pipeline_steps.delivery_mechanism import classify_delivery_mechanism


def _classify(**overrides) -> str:
    base = {
        "heuristic_count": 0,
        "ai_count": 0,
        "rung_count": 0,
        "script_present": False,
        "page_text_length": 5000,
        "site_fetch_failed": False,
        "site_total": 0,
    }
    base.update(overrides)
    return classify_delivery_mechanism(**base)


class TestClassifyDeliveryMechanism:
    def test_unreachable_when_fetch_failed_and_empty(self):
        assert _classify(site_fetch_failed=True, site_total=0) == "unreachable"

    def test_static_listing_for_substantial_anchors(self):
        assert _classify(heuristic_count=175, site_total=175) == "static_listing"

    def test_structured_endpoint_from_rung(self):
        assert _classify(rung_count=55, site_total=55) == "structured_endpoint"

    def test_rung_wins_over_thin_heuristic(self):
        # ≤5 stray anchors but a rung recovered the real list → structured.
        assert _classify(heuristic_count=2, rung_count=149, site_total=149) == "structured_endpoint"

    def test_rung_wins_over_substantial_heuristic(self):
        # General Atlantic: server-renders ~19 partial anchors (heuristic > the
        # substantial-listing threshold) AND a wp-json rung holds the full 406. The
        # authoritative rung must win — not be short-circuited to static_listing.
        assert (
            _classify(heuristic_count=19, rung_count=400, site_total=419)
            == "structured_endpoint"
        )

    def test_embedded_json_when_ai_read_a_script(self):
        assert _classify(ai_count=10, script_present=True, site_total=10) == "embedded_json"

    def test_ai_extracted_without_script(self):
        assert _classify(ai_count=10, script_present=False, site_total=10) == "ai_extracted"

    def test_small_server_rendered_listing(self):
        assert _classify(heuristic_count=3, site_total=3) == "static_listing"

    def test_opaque_shell_when_empty_and_skeletal(self):
        assert _classify(site_total=0, page_text_length=200) == "opaque_shell"

    def test_no_portfolio_found_on_substantive_empty_page(self):
        assert _classify(site_total=0, page_text_length=9000) == "no_portfolio_found"

    def test_site_listing_catch_all(self):
        # Defensive catch-all: a non-zero result with no path attribution. The
        # discovery flow can't produce this (non-zero site_total implies a
        # contributing path), but the classifier stays total over its inputs.
        assert _classify(site_total=5) == "site_listing"
