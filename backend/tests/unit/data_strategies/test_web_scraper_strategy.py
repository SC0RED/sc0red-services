"""Tests for WebScraperStrategy and scrape_url."""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from bs4 import BeautifulSoup

from src.data_strategies.web_scraper_strategy import (
    WebScraperStrategy,
    _extract_context_name,
    _name_from_img_src,
    name_from_url,
    normalize_url,
    scrape_url,
)


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


class TestScrapeUrl:
    @patch("src.data_strategies.web_scraper_strategy.httpx.Client")
    def test_scrape_success(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.text = """
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
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = scrape_url("https://example.com")
        assert result["title"] == "Test Page"
        assert result["description"] == "A test page"
        assert result["meta_keywords"] == "test,page"
        assert "content about a company" in result["text"]
        assert any(link["text"] == "Link Text" for link in result["links"])

    @patch("src.data_strategies.web_scraper_strategy.httpx.Client")
    def test_scrape_fallback_h1_title(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.text = "<html><body><h1>Fallback Title</h1><p>content here</p></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = scrape_url("https://example.com")
        assert result["title"] == "Fallback Title"

    @patch("src.data_strategies.web_scraper_strategy.httpx.Client")
    def test_scrape_og_description_fallback(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.text = (
            '<html><head><meta property="og:description" content="OG Desc"></head>'
            "<body><p>body</p></body></html>"
        )
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = scrape_url("https://example.com")
        assert result["description"] == "OG Desc"

    @patch("src.data_strategies.web_scraper_strategy.httpx.Client")
    def test_scrape_removes_clutter(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.text = (
            "<html><body>"
            "<nav>Navigation</nav>"
            "<footer>Footer</footer>"
            "<script>var x = 1;</script>"
            "<p>Real content here</p>"
            "</body></html>"
        )
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = scrape_url("https://example.com")
        assert "Navigation" not in result["text"]
        assert "var x" not in result["text"]
        assert "Real content" in result["text"]

    @patch("src.data_strategies.web_scraper_strategy.httpx.Client")
    def test_scrape_image_link_fallback(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.text = (
            '<html><body><a href="https://co.com"><img alt="Company Logo"></a></body></html>'
        )
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = scrape_url("https://example.com")
        assert any(link["text"] == "Company Logo" for link in result["links"])

    @patch("src.data_strategies.web_scraper_strategy.httpx.Client")
    def test_scrape_aria_label_fallback(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.text = (
            '<html><body><a href="https://co.com" aria-label="Visit Company"></a></body></html>'
        )
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = scrape_url("https://example.com")
        assert any(link["text"] == "Visit Company" for link in result["links"])

    @patch("src.data_strategies.web_scraper_strategy.httpx.Client")
    def test_scrape_skips_hash_and_mailto_links(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.text = (
            "<html><body>"
            '<a href="#section">Anchor</a>'
            '<a href="mailto:test@test.com">Email</a>'
            '<a href="https://good.com">Good Link</a>'
            "</body></html>"
        )
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

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
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_scrape.side_effect = httpx.HTTPStatusError(
            "Not found",
            request=MagicMock(),
            response=mock_response,
        )
        strategy = WebScraperStrategy(config={"url": "https://example.com"})
        text, meta = strategy.execute()
        assert text == ""
        assert "404" in meta["error"]

    @patch("src.data_strategies.web_scraper_strategy.scrape_url")
    def test_execute_request_error(self, mock_scrape):
        mock_scrape.side_effect = httpx.RequestError("Connection refused", request=MagicMock())
        strategy = WebScraperStrategy(config={"url": "https://example.com"})
        text, meta = strategy.execute()
        assert text == ""
        assert "error" in meta


class TestNameFromImgSrc:
    def test_hyphenated_filename(self):
        assert _name_from_img_src("https://cdn/access-healthcare.png") == "Access Healthcare"

    def test_underscored_filename(self):
        assert _name_from_img_src("access_healthcare.png") == "Access Healthcare"

    def test_camel_case_filename(self):
        assert _name_from_img_src("accessHealthcare.png") == "Access Healthcare"

    def test_single_lowercase_token(self):
        # No separators → can't split; title-cased single token (imperfect but surfaced).
        assert _name_from_img_src("accesshealthcare.png") == "Accesshealthcare"

    def test_strips_logo_suffix(self):
        assert _name_from_img_src("fold-health-logo.png") == "Fold Health"
        assert _name_from_img_src("fold-health_logo.png") == "Fold Health"
        assert _name_from_img_src("fold-healthlogo.png") == "Fold Health"

    def test_handles_full_url_with_path(self):
        src = "https://perotjain.com/wp-content/uploads/2022/09/accesshealthcare.png"
        assert _name_from_img_src(src) == "Accesshealthcare"

    def test_handles_query_string_and_fragment(self):
        assert _name_from_img_src("/img/access-healthcare.png?v=2") == "Access Healthcare"
        assert _name_from_img_src("/img/access-healthcare.png#anchor") == "Access Healthcare"

    def test_no_extension(self):
        assert _name_from_img_src("/img/access-healthcare") == "Access Healthcare"

    def test_empty_returns_empty(self):
        assert _name_from_img_src("") == ""

    def test_short_result_rejected(self):
        # Single char → below min length
        assert _name_from_img_src("/img/a.png") == ""

    def test_too_long_result_rejected(self):
        assert _name_from_img_src(f"/img/{'a' * 80}.png") == ""


class TestNameFromUrl:
    def test_bare_hostname(self):
        assert name_from_url("https://endurancelift.com") == "Endurancelift"

    def test_strips_www(self):
        assert name_from_url("https://www.endurancelift.com/") == "Endurancelift"

    def test_hyphenated_hostname(self):
        assert name_from_url("https://access-healthcare.com") == "Access Healthcare"

    def test_with_path(self):
        assert name_from_url("https://www.endurancelift.com/about") == "Endurancelift"

    def test_missing_scheme_gets_added(self):
        assert name_from_url("endurancelift.com") == "Endurancelift"

    def test_subdomain_stripped_only_if_www(self):
        # Non-www subdomain is kept as part of the hostname stem
        assert name_from_url("https://portfolio.endurancelift.com") == "Portfolio Endurancelift"

    def test_empty_returns_empty(self):
        assert name_from_url("") == ""

    def test_too_long_rejected(self):
        long_host = "a" * 80 + ".com"
        assert name_from_url(f"https://{long_host}") == ""


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
