"""Tests for the WordPress wp-json portfolio discovery rung."""

import json
from unittest.mock import patch

import pytest
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError, RequestException

from src.data_strategies import wp_json_strategy
from src.data_strategies.wp_json_strategy import discover_via_wp_json

_TYPES_WITH_COMPANY = {
    "post": {"name": "Posts", "rest_base": "posts"},
    "page": {"name": "Pages", "rest_base": "pages"},
    # CPT key differs from its REST base on purpose — the rung must use rest_base.
    "company_cpt": {"name": "Portfolio Companies", "rest_base": "company"},
}


def _route(types, items_by_base):
    """Build a fetch_page_html side-effect routing types + CPT pages by URL."""

    def fake(url):
        if url.endswith("/wp-json/wp/v2/types"):
            return json.dumps(types)
        for base, pages in items_by_base.items():
            if f"/wp-json/wp/v2/{base}?" in url:
                page = int(url.split("&page=")[1])  # NB: per_page also contains "page="
                return json.dumps(pages[page - 1] if page - 1 < len(pages) else [])
        return json.dumps([])

    return fake


class TestDiscoverViaWpJson:
    def test_discovers_cpt_maps_title_and_link(self):
        items = [
            {"title": {"rendered": "Acme &amp; Co"}, "link": "https://acme.com"},
            {"title": {"rendered": "Beta Corp"}, "link": "https://beta.com"},
        ]
        fake = _route(_TYPES_WITH_COMPANY, {"company": [items]})
        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake):
            out = discover_via_wp_json("https://firm.com")
        assert [c["name"] for c in out] == ["Acme & Co", "Beta Corp"]  # HTML entity unescaped
        assert out[0]["url"] == "https://acme.com"
        assert all(c["source"] == "site" for c in out)

    def test_not_wordpress_returns_empty(self):
        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=HTTPError("404")):
            assert discover_via_wp_json("https://firm.com") == []

    def test_types_not_json_returns_empty(self):
        with patch.object(
            wp_json_strategy, "fetch_page_html", return_value="<html>not json</html>"
        ):
            assert discover_via_wp_json("https://firm.com") == []

    def test_no_portfolio_cpt_returns_empty(self):
        builtin_only = {"post": {"rest_base": "posts"}, "page": {"rest_base": "pages"}}
        fake = _route(builtin_only, {})
        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake):
            assert discover_via_wp_json("https://firm.com") == []

    def test_paginates_until_short_page(self):
        # _PER_PAGE patched to 2 → page1 full (2), page2 partial (1) → stop after page2.
        pages = [
            [
                {"title": {"rendered": "One"}, "link": "https://one.com"},
                {"title": {"rendered": "Two"}, "link": "https://two.com"},
            ],
            [{"title": {"rendered": "Three"}, "link": "https://three.com"}],
        ]
        fake = _route(_TYPES_WITH_COMPANY, {"company": pages})
        with (
            patch.object(wp_json_strategy, "_PER_PAGE", 2),
            patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake),
        ):
            out = discover_via_wp_json("https://firm.com")
        assert [c["name"] for c in out] == ["One", "Two", "Three"]

    def test_pagination_stops_on_http_error_past_end(self):
        # page1 full (2 of per_page=2), page2 raises HTTP 400 (past end) → stop, keep page1.
        calls = {"n": 0}

        def fake(url):
            if url.endswith("/types"):
                return json.dumps(_TYPES_WITH_COMPANY)
            calls["n"] += 1
            if calls["n"] == 1:
                return json.dumps(
                    [
                        {"title": {"rendered": "One"}, "link": "https://one.com"},
                        {"title": {"rendered": "Two"}, "link": "https://two.com"},
                    ]
                )
            raise HTTPError("400 rest_post_invalid_page_number")

        with (
            patch.object(wp_json_strategy, "_PER_PAGE", 2),
            patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake),
        ):
            out = discover_via_wp_json("https://firm.com")
        assert [c["name"] for c in out] == ["One", "Two"]

    def test_skips_items_missing_name_or_url(self):
        items = [
            {"title": {"rendered": ""}, "link": "https://noname.com"},  # no name
            {"title": {"rendered": "No URL"}, "link": ""},  # no url
            {"title": {"rendered": "Good"}, "link": "https://good.com"},
        ]
        fake = _route(_TYPES_WITH_COMPANY, {"company": [items]})
        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake):
            out = discover_via_wp_json("https://firm.com")
        assert [c["name"] for c in out] == ["Good"]

    def test_impersonate_error_propagates(self):
        # A misconfigured impersonation target is a bug, not a per-site miss.
        with (
            patch.object(wp_json_strategy, "fetch_page_html", side_effect=ImpersonateError("x")),
            pytest.raises(ImpersonateError),
        ):
            discover_via_wp_json("https://firm.com")

    def test_request_exception_on_types_is_soft(self):
        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=RequestException("x")):
            assert discover_via_wp_json("https://firm.com") == []


class TestStatusTagging:
    """wp-json tags current/realized from a status taxonomy (best-effort, fail-open)."""

    def _fake(self):
        def fake(url):
            if url.endswith("/wp-json/wp/v2/types"):
                return json.dumps(_TYPES_WITH_COMPANY)
            if "/wp-json/wp/v2/status-company?" in url:  # taxonomy terms
                return json.dumps([{"id": 25, "name": "Current"}, {"id": 26, "name": "Realized"}])
            if "/wp-json/wp/v2/company?" in url:
                page = int(url.split("&page=")[1])
                if page == 1:
                    return json.dumps(
                        [
                            {
                                "title": {"rendered": "Acme"},
                                "link": "https://acme.com",
                                "status-company": [25],
                            },
                            {
                                "title": {"rendered": "OldCo"},
                                "link": "https://oldco.com",
                                "status-company": [26],
                            },
                        ]
                    )
                return json.dumps([])
            return json.dumps([])

        return fake

    def test_tags_current_and_realized(self):
        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=self._fake()):
            out = discover_via_wp_json("https://firm.com")
        by_name = {c["name"]: c["status"] for c in out}
        assert by_name == {"Acme": "current", "OldCo": "realized"}

    def test_no_status_taxonomy_leaves_status_empty(self):
        # A non-status taxonomy (sector) whose terms carry no realized/current
        # keyword must NOT be treated as the status taxonomy → status "".
        def fake(url):
            if url.endswith("/wp-json/wp/v2/types"):
                return json.dumps(_TYPES_WITH_COMPANY)
            if "/wp-json/wp/v2/sector?" in url:
                return json.dumps([{"id": 7, "name": "Healthcare"}, {"id": 8, "name": "Software"}])
            if "/wp-json/wp/v2/company?" in url:
                page = int(url.split("&page=")[1])
                if page == 1:
                    return json.dumps(
                        [{"title": {"rendered": "Acme"}, "link": "https://acme.com", "sector": [7]}]
                    )
                return json.dumps([])
            return json.dumps([])

        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake):
            out = discover_via_wp_json("https://firm.com")
        assert out[0]["status"] == ""

    def test_requires_both_current_and_realized(self):
        # A taxonomy with a stray realized-ish word but no current term must NOT
        # be chosen as the status taxonomy (e.g. a "Former Industries" sector).
        def fake(url):
            if url.endswith("/wp-json/wp/v2/types"):
                return json.dumps(_TYPES_WITH_COMPANY)
            if "/wp-json/wp/v2/stage?" in url:
                return json.dumps(
                    [{"id": 1, "name": "Former Industries"}, {"id": 2, "name": "Healthcare"}]
                )
            if "/wp-json/wp/v2/company?" in url:
                page = int(url.split("&page=")[1])
                if page == 1:
                    return json.dumps(
                        [{"title": {"rendered": "Acme"}, "link": "https://acme.com", "stage": [1]}]
                    )
                return json.dumps([])
            return json.dumps([])

        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake):
            out = discover_via_wp_json("https://firm.com")
        assert out[0]["status"] == ""  # not mis-tagged realized

    def test_probes_taxonomy_once_not_per_page(self):
        # Regression: a no-status firm with a multi-page CPT must probe its
        # taxonomies exactly once (on page 1), not on every page.
        calls = {"sector": 0}

        def fake(url):
            if url.endswith("/wp-json/wp/v2/types"):
                return json.dumps(_TYPES_WITH_COMPANY)
            if "/wp-json/wp/v2/sector?" in url:
                calls["sector"] += 1
                return json.dumps([{"id": 7, "name": "Healthcare"}])
            if "/wp-json/wp/v2/company?" in url:
                page = int(url.split("&page=")[1])
                if page <= 2:  # two full pages (per_page patched to 2)
                    return json.dumps(
                        [
                            {
                                "title": {"rendered": f"C{page}a"},
                                "link": f"https://c{page}a.com",
                                "sector": [7],
                            },
                            {
                                "title": {"rendered": f"C{page}b"},
                                "link": f"https://c{page}b.com",
                                "sector": [7],
                            },
                        ]
                    )
                return json.dumps([])
            return json.dumps([])

        with (
            patch.object(wp_json_strategy, "_PER_PAGE", 2),
            patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake),
        ):
            discover_via_wp_json("https://firm.com")
        assert calls["sector"] == 1

    def test_detects_status_when_first_item_untagged(self):
        # Regression (CodeRabbit): items[0] has no status terms but items[1] does
        # → the taxonomy is still detected (scan all page items, not just the first).
        def fake(url):
            if url.endswith("/wp-json/wp/v2/types"):
                return json.dumps(_TYPES_WITH_COMPANY)
            if "/wp-json/wp/v2/status-company?" in url:
                return json.dumps([{"id": 25, "name": "Current"}, {"id": 26, "name": "Realized"}])
            if "/wp-json/wp/v2/company?" in url:
                page = int(url.split("&page=")[1])
                if page == 1:
                    return json.dumps(
                        [
                            {
                                "title": {"rendered": "Untagged"},
                                "link": "https://untagged.com",
                                "status-company": [],
                            },
                            {
                                "title": {"rendered": "OldCo"},
                                "link": "https://oldco.com",
                                "status-company": [26],
                            },
                        ]
                    )
                return json.dumps([])
            return json.dumps([])

        with patch.object(wp_json_strategy, "fetch_page_html", side_effect=fake):
            out = discover_via_wp_json("https://firm.com")
        assert {c["name"]: c["status"] for c in out} == {"Untagged": "", "OldCo": "realized"}
