"""Tests for JanusEvent model."""

from src.models.model_event import JanusEvent


class TestJanusEvent:
    def test_create_company_analysis(self):
        event = JanusEvent(
            request_id="req-123",
            request_type="company_analysis",
            url="https://example.com",
            tenant_id="tenant-1",
            org_id="org-1",
            user_id="user-1",
        )
        assert event.request_id == "req-123"
        assert event.request_type == "company_analysis"
        assert event.scan_id == ""
        assert event.extra == {}

    def test_create_portfolio_scan(self):
        event = JanusEvent(
            request_id="req-456",
            request_type="portfolio_scan",
            url="https://pe-firm.com",
            tenant_id="tenant-1",
            org_id="org-1",
            user_id="user-1",
            scan_id="scan-789",
        )
        assert event.request_type == "portfolio_scan"
        assert event.scan_id == "scan-789"

    def test_extra_dict(self):
        event = JanusEvent(
            request_id="req-1",
            request_type="company_analysis",
            url="https://example.com",
            extra={"source": "manual"},
        )
        assert event.extra["source"] == "manual"

    def test_defaults(self):
        event = JanusEvent()
        assert event.request_id == ""
        assert event.request_type == ""
        assert event.url == ""
