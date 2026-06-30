"""Tests for the sitemap portfolio discovery rung."""

from unittest.mock import patch

import pytest
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError

from src.data_strategies import sitemap_strategy
from src.data_strategies.sitemap_strategy import discover_via_sitemap


def _sitemap(*locs):
    body = "".join(f"<url><loc>{loc}</loc></url>" for loc in locs)
    return f'<?xml version="1.0"?><urlset>{body}</urlset>'


def _index(*locs):
    body = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in locs)
    return f'<?xml version="1.0"?><sitemapindex>{body}</sitemapindex>'


class TestDiscoverViaSitemap:
    def test_enumerates_portfolio_detail_pages(self):
        xml = _sitemap(
            "https://audax.com/portfolio/48forty-solutions",
            "https://audax.com/portfolio/aamp-global",
            "https://audax.com/about",  # not a company detail page → filtered
            "https://audax.com/portfolio",  # listing index, no slug → filtered
        )
        with patch.object(sitemap_strategy, "fetch_page_html", return_value=xml):
            out = discover_via_sitemap("https://audax.com")
        assert [c["name"] for c in out] == ["48forty Solutions", "Aamp Global"]
        assert out[0]["url"] == "https://audax.com/portfolio/48forty-solutions"
        assert all(c["source"] == "site" for c in out)

    def test_handles_hyphenated_section(self):
        # Riverside-style /investment-portfolio/<slug>.
        xml = _sitemap("https://riverside.com/investment-portfolio/whatcounts")
        with patch.object(sitemap_strategy, "fetch_page_html", return_value=xml):
            out = discover_via_sitemap("https://riverside.com")
        assert out == [
            {
                "name": "Whatcounts",
                "url": "https://riverside.com/investment-portfolio/whatcounts",
                "description": "",
                "source": "site",
            }
        ]

    def test_follows_sitemap_index_one_level(self):
        index = _index(
            "https://firm.com/page-sitemap.xml",
            "https://firm.com/portfolio-sitemap.xml",
        )
        child = _sitemap("https://firm.com/companies/acme")

        def fake(url):
            if url.endswith("/sitemap.xml"):
                return index
            if "portfolio-sitemap" in url:
                return child
            return _sitemap()  # other child sitemaps empty

        with patch.object(sitemap_strategy, "fetch_page_html", side_effect=fake):
            out = discover_via_sitemap("https://firm.com")
        assert [c["name"] for c in out] == ["Acme"]

    def test_dedupes_by_url(self):
        xml = _sitemap(
            "https://firm.com/companies/acme",
            "https://firm.com/companies/acme?utm=x",  # same page, query stripped
        )
        with patch.object(sitemap_strategy, "fetch_page_html", return_value=xml):
            out = discover_via_sitemap("https://firm.com")
        assert len(out) == 1

    def test_no_sitemap_returns_empty(self):
        with patch.object(sitemap_strategy, "fetch_page_html", side_effect=HTTPError("404")):
            assert discover_via_sitemap("https://firm.com") == []

    def test_sitemap_without_company_pages_returns_empty(self):
        xml = _sitemap("https://firm.com/about", "https://firm.com/team/jane-doe")
        with patch.object(sitemap_strategy, "fetch_page_html", return_value=xml):
            assert discover_via_sitemap("https://firm.com") == []

    def test_impersonate_error_propagates(self):
        with (
            patch.object(sitemap_strategy, "fetch_page_html", side_effect=ImpersonateError("x")),
            pytest.raises(ImpersonateError),
        ):
            discover_via_sitemap("https://firm.com")
