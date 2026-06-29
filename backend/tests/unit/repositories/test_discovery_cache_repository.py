"""Tests for DiscoveryCacheRepository — the per-domain proven-path cache."""

from unittest.mock import MagicMock

from src.repositories.dynamodb.discovery_cache_repository import (
    CACHE_TTL_DAYS,
    DiscoveryCacheRepository,
    domain_of,
)


class TestDomainOf:
    def test_strips_scheme_www_and_path(self):
        assert domain_of("https://www.kohlberg.com/investments/") == "kohlberg.com"

    def test_bare_host(self):
        assert domain_of("vista.com") == "vista.com"

    def test_no_host_returns_empty(self):
        # Path-only / empty inputs have no netloc → no cache key.
        assert domain_of("") == ""
        assert domain_of("/just/a/path") == ""


class TestGetProvenPath:
    def test_returns_none_when_absent(self):
        table = MagicMock()
        table.get_item.return_value = None
        repo = DiscoveryCacheRepository(table)
        assert repo.get_proven_path("https://firm.com") is None
        table.get_item.assert_called_once_with(pk="DISCOVERY_CACHE#firm.com", sk="PROVEN_PATH")

    def test_returns_none_for_hostless_url_without_a_read(self):
        table = MagicMock()
        repo = DiscoveryCacheRepository(table)
        assert repo.get_proven_path("") is None
        table.get_item.assert_not_called()

    def test_maps_stored_item(self):
        table = MagicMock()
        table.get_item.return_value = {
            "pk": "DISCOVERY_CACHE#firm.com",
            "sk": "PROVEN_PATH",
            "source": "wp_json",
            "count": 55,
            "mechanism": "structured_endpoint",
            "ttl": 1234,
        }
        repo = DiscoveryCacheRepository(table)
        assert repo.get_proven_path("https://firm.com/x") == {
            "source": "wp_json",
            "count": 55,
            "mechanism": "structured_endpoint",
        }


class TestPutProvenPath:
    def test_writes_item_with_ttl(self):
        table = MagicMock()
        repo = DiscoveryCacheRepository(table)
        repo.put_proven_path(
            "https://www.firm.com/portfolio",
            source="sitemap",
            count=42,
            mechanism="structured_endpoint",
        )
        item = table.put_item.call_args[0][0]
        assert item["pk"] == "DISCOVERY_CACHE#firm.com"
        assert item["sk"] == "PROVEN_PATH"
        assert item["source"] == "sitemap"
        assert item["count"] == 42
        # TTL is epoch-seconds in the future (within the configured window).
        assert item["ttl"] > 0

    def test_ignores_non_structured_source(self):
        table = MagicMock()
        repo = DiscoveryCacheRepository(table)
        repo.put_proven_path(
            "https://firm.com", source="web_search", count=9, mechanism="ai_extracted"
        )
        table.put_item.assert_not_called()

    def test_ignores_hostless_url(self):
        table = MagicMock()
        repo = DiscoveryCacheRepository(table)
        repo.put_proven_path("", source="wp_json", count=9, mechanism="structured_endpoint")
        table.put_item.assert_not_called()

    def test_ttl_window_is_configured_days_ahead(self):
        import time

        table = MagicMock()
        repo = DiscoveryCacheRepository(table)
        before = int(time.time())
        repo.put_proven_path("https://firm.com", source="wp_json", count=9, mechanism="x")
        ttl = table.put_item.call_args[0][0]["ttl"]
        assert (
            before + CACHE_TTL_DAYS * 86400 <= ttl <= int(time.time()) + CACHE_TTL_DAYS * 86400 + 5
        )
