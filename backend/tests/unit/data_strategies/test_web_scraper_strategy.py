"""Tests for WebScraperStrategy and scrape_url."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError

from src.data_strategies.scraper_names import (
    extract_name_from_img_src,
    extract_name_from_url,
    name_from_url_slug,
)
from src.data_strategies.web_scraper_strategy import (
    WebScraperStrategy,
    _extract_context_name,
    _extract_embedded_companies,
    normalize_url,
    scrape_url,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _http_error(status_code: int) -> HTTPError:
    """Build a curl_cffi HTTPError whose .response carries a status code."""
    error = HTTPError(f"HTTP Error {status_code}")
    error.response = MagicMock(status_code=status_code)
    return error


class TestExtractEmbeddedCompanies:
    def test_extracts_escaped_json_records(self):
        # SSR/headless-CMS shape: stringified JSON with escaped quotes, each
        # company record large with logo/timestamp noise around name+slug.
        html = (
            "<html><head><script>"
            'self.__next_f.push([1,"{\\"items\\":['
            r"{\"name\":\"Calabrio\",\"slug\":\"calabrio\","
            r"\"logoSolidBlack\":{\"alt\":\"Calabrio logo\",\"filename\":\"x.svg\"}},"
            r"{\"name\":\"ABC Fitness Solutions\",\"slug\":\"abc\",\"updatedAt\":\"2025-11-19\"},"
            r"{\"name\":\"Dynatrace\",\"slug\":\"dynatrace\"}"
            ']}"])</script></head><body></body></html>'
        )
        out = _extract_embedded_companies(_soup(html))
        names = {c["name"] for c in out}
        slugs = {c["slug"] for c in out}
        assert names == {"Calabrio", "ABC Fitness Solutions", "Dynatrace"}
        assert slugs == {"calabrio", "abc", "dynatrace"}

    def test_extracts_plain_json_records(self):
        html = (
            "<html><head><script>"
            'window.__DATA__ = {"companies":['
            '{"name":"Acme Corp","slug":"acme"},'
            '{"name":"Globex","slug":"globex"}]}'
            "</script></head><body></body></html>"
        )
        out = _extract_embedded_companies(_soup(html))
        assert {c["slug"] for c in out} == {"acme", "globex"}

    def test_excludes_name_without_adjacent_slug(self):
        # Logo asset (name but no slug) and searchableNormalized (name, no slug)
        # must NOT be mistaken for companies.
        html = (
            "<html><head><script>"
            r"{\"logo\":{\"name\":\"some-logo\",\"filename\":\"logo.svg\"},"
            r"\"searchableNormalized\":{\"name\":\"bottomline\"}}"
            "</script></head><body></body></html>"
        )
        assert _extract_embedded_companies(_soup(html)) == []

    def test_dedupes_by_slug(self):
        html = (
            "<html><head><script>"
            '{"a":{"name":"Acme","slug":"acme"},"b":{"name":"Acme Dup","slug":"acme"}}'
            "</script></head><body></body></html>"
        )
        out = _extract_embedded_companies(_soup(html))
        assert len(out) == 1
        assert out[0]["slug"] == "acme"

    def test_no_records_returns_empty(self):
        html = "<html><head><script>console.log('hi')</script></head><body><p>x</p></body></html>"
        assert _extract_embedded_companies(_soup(html)) == []

    def test_skips_external_scripts(self):
        html = '<html><head><script src="https://cdn/app.js"></script></head><body></body></html>'
        assert _extract_embedded_companies(_soup(html)) == []


class TestNormalizeUrl:
    def test_full_url(self):
        assert normalize_url("https://example.com/path") == "https://example.com/path"

    def test_no_protocol(self):
        assert normalize_url("example.com/path") == "https://example.com/path"

    def test_http_preserved(self):
        assert normalize_url("http://example.com/path") == "http://example.com/path"

    def test_strips_query_and_fragment(self):
        result = normalize_url("https://example.com/path?q=1#section")
        assert result == "https://example.com/path"

    def test_trailing_slash(self):
        result = normalize_url("https://example.com/")
        assert result == "https://example.com/"


def _patch_html(html: str):
    """Patch the transport so scrape_url parses the given HTML."""
    return patch(
        "src.data_strategies.web_scraper_strategy.fetch_page_html",
        return_value=html,
    )


class TestScrapeUrl:
    def test_scrape_success(self):
        html = """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="A test page">
            <meta name="keywords" content="test,page">
        </head>
        <body>
            <h1>Welcome</h1>
            <p>This is some content about a company that does interesting things.</p>
            <a href="https://other.com">Link Text</a>
        </body>
        </html>
        """
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert result["title"] == "Test Page"
        assert result["description"] == "A test page"
        assert result["meta_keywords"] == "test,page"
        assert "content about a company" in result["text"]
        assert any(link["text"] == "Link Text" for link in result["links"])

    def test_scrape_fallback_h1_title(self):
        html = "<html><body><h1>Fallback Title</h1><p>content here</p></body></html>"
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert result["title"] == "Fallback Title"

    def test_scrape_og_description_fallback(self):
        html = (
            '<html><head><meta property="og:description" content="OG Desc"></head>'
            "<body><p>body</p></body></html>"
        )
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert result["description"] == "OG Desc"

    def test_scrape_removes_clutter(self):
        html = (
            "<html><body>"
            "<nav>Navigation</nav>"
            "<footer>Footer</footer>"
            "<script>var x = 1;</script>"
            "<p>Real content here</p>"
            "</body></html>"
        )
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert "Navigation" not in result["text"]
        assert "var x" not in result["text"]
        assert "Real content" in result["text"]

    def test_scrape_removes_element_with_exact_clutter_class(self):
        """Element with class exactly matching 'sidebar' is removed."""
        html = (
            '<html><body><div class="sidebar">Sidebar junk</div><p>Main content</p></body></html>'
        )
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert "Sidebar junk" not in result["text"]
        assert "Main content" in result["text"]

    def test_scrape_preserves_compound_class_with_clutter_substring(self):
        """Element with class 'no-sidebar' is NOT removed — token matching, not substring."""
        html = (
            '<html><body class="home no-sidebar wp-theme">'
            "<p>Important content about the company</p>"
            "</body></html>"
        )
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert "Important content" in result["text"]

    def test_scrape_never_removes_body_element(self):
        """<body> is never decomposed even if its class matches a clutter keyword."""
        html = (
            '<html><body class="sidebar">'
            "<p>Content inside body with sidebar class</p>"
            "</body></html>"
        )
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert "Content inside body" in result["text"]

    def test_scrape_image_link_fallback(self):
        html = '<html><body><a href="https://co.com"><img alt="Company Logo"></a></body></html>'
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert any(link["text"] == "Company Logo" for link in result["links"])

    def test_scrape_aria_label_fallback(self):
        html = '<html><body><a href="https://co.com" aria-label="Visit Company"></a></body></html>'
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert any(link["text"] == "Visit Company" for link in result["links"])

    def test_scrape_returns_embedded_companies(self):
        html = (
            "<html><head><script>"
            '{"items":[{"name":"Acme Corp","slug":"acme"},{"name":"Globex","slug":"globex"}]}'
            "</script></head><body><p>skeleton</p></body></html>"
        )
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert {c["slug"] for c in result["embedded_companies"]} == {"acme", "globex"}
        # existing keys still present
        assert "text" in result and "links" in result and "script_text" in result

    def test_scrape_returns_logo_company_names(self):
        html = (
            "<html><body>"
            '<img alt="Logo of software company Jamf">'
            '<img alt="Logo of software company Datto">'
            "<p>skeleton</p></body></html>"
        )
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert result["logo_company_names"] == ["Jamf", "Datto"]

    def test_scrape_skips_hash_and_mailto_links(self):
        html = (
            "<html><body>"
            '<a href="#section">Anchor</a>'
            '<a href="mailto:test@test.com">Email</a>'
            '<a href="https://good.com">Good Link</a>'
            "</body></html>"
        )
        with _patch_html(html):
            result = scrape_url("https://example.com")
        assert len(result["links"]) == 1
        assert result["links"][0]["text"] == "Good Link"


class TestWebScraperStrategy:
    def test_execute_no_url(self):
        strategy = WebScraperStrategy(config={})
        text, meta = strategy.execute()
        assert text == ""
        assert meta["error"] == "No URL provided"

    @patch("src.data_strategies.web_scraper_strategy.scrape_url")
    def test_execute_success(self, mock_scrape):
        mock_scrape.return_value = {
            "text": "Page content here",
            "title": "Title",
            "description": "Desc",
            "links": [{"text": "Link", "href": "https://link.com"}],
            "meta_keywords": "key1",
        }
        strategy = WebScraperStrategy(config={"url": "https://example.com"})
        text, meta = strategy.execute()
        assert text == "Page content here"
        assert meta["title"] == "Title"
        assert meta["description"] == "Desc"

    @patch("src.data_strategies.web_scraper_strategy.scrape_url")
    def test_execute_http_error(self, mock_scrape):
        mock_scrape.side_effect = _http_error(404)
        strategy = WebScraperStrategy(config={"url": "https://example.com"})
        text, meta = strategy.execute()
        assert text == ""
        assert "404" in meta["error"]

    @patch("src.data_strategies.web_scraper_strategy.scrape_url")
    def test_execute_http_error_without_response(self, mock_scrape):
        # Defensive branch: HTTPError with no .response → degrade to the error
        # string rather than crash on "HTTP None".
        error = HTTPError("boom")
        error.response = None
        mock_scrape.side_effect = error
        strategy = WebScraperStrategy(config={"url": "https://example.com"})
        text, meta = strategy.execute()
        assert text == ""
        assert meta["error"] == "boom"

    @patch("src.data_strategies.web_scraper_strategy.scrape_url")
    def test_execute_request_error(self, mock_scrape):
        mock_scrape.side_effect = CurlConnectionError("Connection refused")
        strategy = WebScraperStrategy(config={"url": "https://example.com"})
        text, meta = strategy.execute()
        assert text == ""
        assert "error" in meta

    @patch("src.data_strategies.web_scraper_strategy.scrape_url")
    def test_execute_impersonation_misconfig_propagates(self, mock_scrape):
        # A bad _IMPERSONATE_TARGET is a programming/config error — it must crash
        # loudly, not be swallowed into the ("", {"error": ...}) transport contract.
        mock_scrape.side_effect = ImpersonateError("bad target")
        strategy = WebScraperStrategy(config={"url": "https://example.com"})
        with pytest.raises(ImpersonateError):
            strategy.execute()


class TestNameFromImgSrc:
    def test_hyphenated_filename(self):
        assert (
            extract_name_from_img_src("https://cdn/access-healthcare.png") == "Access Healthcare"
        )

    def test_underscored_filename(self):
        assert extract_name_from_img_src("access_healthcare.png") == "Access Healthcare"

    def test_camel_case_filename(self):
        assert extract_name_from_img_src("accessHealthcare.png") == "Access Healthcare"

    def test_single_lowercase_token(self):
        # No separators → can't split; title-cased single token (imperfect but surfaced).
        assert extract_name_from_img_src("accesshealthcare.png") == "Accesshealthcare"

    def test_strips_logo_suffix(self):
        assert extract_name_from_img_src("fold-health-logo.png") == "Fold Health"
        assert extract_name_from_img_src("fold-health_logo.png") == "Fold Health"
        assert extract_name_from_img_src("fold-healthlogo.png") == "Fold Health"

    def test_handles_full_url_with_path(self):
        src = "https://perotjain.com/wp-content/uploads/2022/09/accesshealthcare.png"
        assert extract_name_from_img_src(src) == "Accesshealthcare"

    def test_handles_query_string_and_fragment(self):
        assert extract_name_from_img_src("/img/access-healthcare.png?v=2") == "Access Healthcare"
        assert (
            extract_name_from_img_src("/img/access-healthcare.png#anchor") == "Access Healthcare"
        )

    def test_no_extension(self):
        assert extract_name_from_img_src("/img/access-healthcare") == "Access Healthcare"

    def test_empty_returns_empty(self):
        assert extract_name_from_img_src("") == ""

    def test_short_result_rejected(self):
        # Single char → below min length
        assert extract_name_from_img_src("/img/a.png") == ""

    def test_too_long_result_rejected(self):
        assert extract_name_from_img_src(f"/img/{'a' * 80}.png") == ""


class TestNameFromUrl:
    def test_bare_hostname(self):
        assert extract_name_from_url("https://endurancelift.com") == "Endurancelift"

    def test_strips_www(self):
        assert extract_name_from_url("https://www.endurancelift.com/") == "Endurancelift"

    def test_hyphenated_hostname(self):
        assert extract_name_from_url("https://access-healthcare.com") == "Access Healthcare"

    def test_with_path(self):
        assert extract_name_from_url("https://www.endurancelift.com/about") == "Endurancelift"

    def test_missing_scheme_gets_added(self):
        assert extract_name_from_url("endurancelift.com") == "Endurancelift"

    def test_subdomain_stripped_only_if_www(self):
        # Non-www subdomain is kept as part of the hostname stem
        assert (
            extract_name_from_url("https://portfolio.endurancelift.com")
            == "Portfolio Endurancelift"
        )

    def test_empty_returns_empty(self):
        assert extract_name_from_url("") == ""

    def test_too_long_rejected(self):
        long_host = "a" * 80 + ".com"
        assert extract_name_from_url(f"https://{long_host}") == ""


class TestExtractContextNameImgSrcFallback:
    """The perotjain-style DOM: logo image has empty alt, name lives in filename."""

    def _anchor(self, html: str) -> Any:
        soup = BeautifulSoup(html, "html.parser")
        return soup.find("a")

    def test_empty_alt_falls_back_to_img_src(self):
        html = """
        <article class="single-card">
          <div class="overlay-content">
            <img alt="" src="/wp-content/uploads/endurance-lift.png">
            <div class="card-text">
              <a class="btn-arrow" href="https://endurancelift.com/">LEARN MORE</a>
            </div>
          </div>
        </article>
        """
        assert _extract_context_name(self._anchor(html)) == "Endurance Lift"

    def test_missing_alt_attribute_falls_back_to_img_src(self):
        html = """
        <article>
          <img src="/img/fold-health-logo.png">
          <a href="https://fold.health">LEARN MORE</a>
        </article>
        """
        assert _extract_context_name(self._anchor(html)) == "Fold Health"

    def test_non_empty_alt_still_wins_over_src(self):
        # Non-empty alt takes precedence — src is only a fallback.
        html = """
        <article>
          <img alt="Access Healthcare" src="/img/something-else.png">
          <a href="https://accesshealthcare.com">LEARN MORE</a>
        </article>
        """
        assert _extract_context_name(self._anchor(html)) == "Access Healthcare"

    def test_no_img_returns_empty(self):
        html = """
        <article>
          <a href="https://example.com">LEARN MORE</a>
        </article>
        """
        assert _extract_context_name(self._anchor(html)) == ""

    def test_all_caps_alt_is_apostrophe_safe_title_cased(self):
        # ALL-CAPS alt is re-cased, but NOT with str.title() (which would yield
        # "Harry'S"). The apostrophe-safe normaliser keeps the trailing s lowercase.
        html = """
        <article>
          <img alt="HARRY'S FRESH FOODS" src="/img/x.png">
          <a href="https://harrys.com">LEARN MORE</a>
        </article>
        """
        assert _extract_context_name(self._anchor(html)) == "Harry's Fresh Foods"

    def test_mixed_case_alt_is_left_untouched(self):
        # Already human-cased alt is trusted verbatim (no "Harry's" → "Harry'S").
        html = """
        <article>
          <img alt="Harry's Fresh Foods" src="/img/x.png">
          <a href="https://harrys.com">LEARN MORE</a>
        </article>
        """
        assert _extract_context_name(self._anchor(html)) == "Harry's Fresh Foods"


class TestNameFromUrlSlug:
    def test_derives_title_cased_name_from_last_segment(self):
        assert name_from_url_slug("https://x.com/investments/aeries-software") == "Aeries Software"

    def test_ignores_trailing_slash(self):
        assert name_from_url_slug("https://x.com/portfolio/acme-corp/") == "Acme Corp"

    def test_returns_empty_when_slug_too_short(self):
        # Single-char stem is below the shared MIN_NAME_LENGTH bound.
        assert name_from_url_slug("https://x.com/portfolio/a") == ""

    def test_returns_empty_for_no_path(self):
        assert name_from_url_slug("https://x.com") == ""
