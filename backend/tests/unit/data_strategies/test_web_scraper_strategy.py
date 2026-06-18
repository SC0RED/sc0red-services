"""Tests for WebScraperStrategy and scrape_url."""

from typing import Any
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.requests.exceptions import HTTPError

from src.data_strategies.web_scraper_strategy import (
    _IMPERSONATE_TARGET,
    WebScraperStrategy,
    _extract_context_name,
    _extract_name_from_img_src,
    extract_name_from_url,
    fetch_page_html,
    normalize_url,
    scrape_url,
)


def _http_error(status_code: int) -> HTTPError:
    """Build a curl_cffi HTTPError whose .response carries a status code."""
    error = HTTPError(f"HTTP Error {status_code}")
    error.response = MagicMock(status_code=status_code)
    return error


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


class TestFetchPageHtml:
    @patch("src.data_strategies.web_scraper_strategy.curl_requests.get")
    def test_impersonates_and_returns_text(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body>hi</body></html>"
        mock_get.return_value = mock_response

        html = fetch_page_html("https://example.com")
        assert html == "<html><body>hi</body></html>"
        # Sole transport: curl_cffi with a browser impersonation target + redirects.
        _args, kwargs = mock_get.call_args
        assert kwargs["impersonate"] == _IMPERSONATE_TARGET
        assert kwargs["allow_redirects"] is True
        mock_response.raise_for_status.assert_called_once()

    @patch("src.data_strategies.web_scraper_strategy.curl_requests.get")
    def test_raises_on_bad_status(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = _http_error(403)
        mock_get.return_value = mock_response

        try:
            fetch_page_html("https://example.com")
        except HTTPError as error:
            assert error.response.status_code == 403
        else:
            raise AssertionError("expected HTTPError")


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


class TestNameFromImgSrc:
    def test_hyphenated_filename(self):
        assert (
            _extract_name_from_img_src("https://cdn/access-healthcare.png") == "Access Healthcare"
        )

    def test_underscored_filename(self):
        assert _extract_name_from_img_src("access_healthcare.png") == "Access Healthcare"

    def test_camel_case_filename(self):
        assert _extract_name_from_img_src("accessHealthcare.png") == "Access Healthcare"

    def test_single_lowercase_token(self):
        # No separators → can't split; title-cased single token (imperfect but surfaced).
        assert _extract_name_from_img_src("accesshealthcare.png") == "Accesshealthcare"

    def test_strips_logo_suffix(self):
        assert _extract_name_from_img_src("fold-health-logo.png") == "Fold Health"
        assert _extract_name_from_img_src("fold-health_logo.png") == "Fold Health"
        assert _extract_name_from_img_src("fold-healthlogo.png") == "Fold Health"

    def test_handles_full_url_with_path(self):
        src = "https://perotjain.com/wp-content/uploads/2022/09/accesshealthcare.png"
        assert _extract_name_from_img_src(src) == "Accesshealthcare"

    def test_handles_query_string_and_fragment(self):
        assert _extract_name_from_img_src("/img/access-healthcare.png?v=2") == "Access Healthcare"
        assert (
            _extract_name_from_img_src("/img/access-healthcare.png#anchor") == "Access Healthcare"
        )

    def test_no_extension(self):
        assert _extract_name_from_img_src("/img/access-healthcare") == "Access Healthcare"

    def test_empty_returns_empty(self):
        assert _extract_name_from_img_src("") == ""

    def test_short_result_rejected(self):
        # Single char → below min length
        assert _extract_name_from_img_src("/img/a.png") == ""

    def test_too_long_result_rejected(self):
        assert _extract_name_from_img_src(f"/img/{'a' * 80}.png") == ""


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
