"""Tests for the browser-impersonating scrape transport + retry."""

from unittest.mock import MagicMock, patch

import pytest
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError

from src.data_strategies.scraper_transport import (
    _FETCH_MAX_ATTEMPTS,
    _IMPERSONATE_TARGET,
    _MAX_REDIRECTS,
    _SCRAPER_TIMEOUT,
    fetch_page_html,
)
from src.data_strategies.url_safety import UnsafeUrlError


def _http_error(status_code: int) -> HTTPError:
    error = HTTPError(f"HTTP Error {status_code}")
    error.response = MagicMock(status_code=status_code)
    return error


def _ok(text: str = "<html><body>hi</body></html>") -> MagicMock:
    response = MagicMock()
    response.text = text
    response.status_code = 200
    response.raise_for_status = MagicMock()
    return response


def _redirect(location: str, status_code: int = 302) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"location": location}
    response.raise_for_status = MagicMock()  # 3xx does not raise
    return response


# The SSRF guard is exercised in test_url_safety; here it is mocked to a no-op so
# the transport tests stay network-free and focused on retry/redirect behaviour.
@patch("src.data_strategies.scraper_transport.assert_public_url")
@patch("src.data_strategies.scraper_transport.time.sleep")  # don't actually back off
@patch("src.data_strategies.scraper_transport.curl_requests.get")
class TestFetchPageHtml:
    def test_success_passes_impersonation_args(self, mock_get, _sleep, _guard):
        mock_get.return_value = _ok()
        html = fetch_page_html("https://example.com")
        assert html == "<html><body>hi</body></html>"
        _args, kwargs = mock_get.call_args
        assert kwargs["impersonate"] == _IMPERSONATE_TARGET
        assert kwargs["timeout"] == _SCRAPER_TIMEOUT
        # Redirects are followed manually (per-hop guarded), not by libcurl.
        assert kwargs["allow_redirects"] is False
        assert mock_get.call_count == 1  # no retry on success

    def test_retries_then_succeeds_on_transient_block(self, mock_get, _sleep, _guard):
        # First attempt 403 (Cloudflare challenge), second returns 200.
        blocked = MagicMock()
        blocked.raise_for_status.side_effect = _http_error(403)
        mock_get.side_effect = [blocked, _ok()]
        assert fetch_page_html("https://example.com") == "<html><body>hi</body></html>"
        assert mock_get.call_count == 2
        assert _sleep.call_count == 1  # one backoff between the two attempts

    def test_not_found_is_not_retried(self, mock_get, _sleep, _guard):
        nf = MagicMock()
        nf.raise_for_status.side_effect = _http_error(404)
        mock_get.return_value = nf
        with pytest.raises(HTTPError):
            fetch_page_html("https://example.com")
        assert mock_get.call_count == 1  # 404 → no retry

    def test_persistent_block_raises_after_max_attempts(self, mock_get, _sleep, _guard):
        blocked = MagicMock()
        blocked.raise_for_status.side_effect = _http_error(403)
        mock_get.return_value = blocked
        with pytest.raises(HTTPError):
            fetch_page_html("https://example.com")
        assert mock_get.call_count == _FETCH_MAX_ATTEMPTS
        assert _sleep.call_count == _FETCH_MAX_ATTEMPTS - 1  # no backoff after the last attempt

    def test_connection_error_is_retried(self, mock_get, _sleep, _guard):
        mock_get.side_effect = [CurlConnectionError("boom"), _ok()]
        assert fetch_page_html("https://example.com") == "<html><body>hi</body></html>"
        assert mock_get.call_count == 2

    def test_impersonate_error_not_retried(self, mock_get, _sleep, _guard):
        mock_get.side_effect = ImpersonateError("bad target")
        with pytest.raises(ImpersonateError):
            fetch_page_html("https://example.com")
        assert mock_get.call_count == 1  # programming error → propagate immediately

    def test_follows_redirect_to_public_url(self, mock_get, _sleep, mock_guard):
        # 302 → final 200. Both hops are validated and followed.
        mock_get.side_effect = [_redirect("https://example.com/real"), _ok("final")]
        assert fetch_page_html("https://example.com") == "final"
        assert mock_get.call_count == 2
        # The guard ran on the original URL and on the redirect target.
        assert mock_guard.call_count == 2
        assert mock_guard.call_args_list[1].args[0] == "https://example.com/real"

    def test_redirect_to_blocked_target_is_refused(self, mock_get, _sleep, mock_guard):
        # The guard passes the first URL, then rejects the redirect target.
        mock_guard.side_effect = [None, UnsafeUrlError("blocked")]
        mock_get.return_value = _redirect("http://169.254.169.254/latest/meta-data/")
        with pytest.raises(UnsafeUrlError):
            fetch_page_html("https://example.com")
        # Only the first hop was fetched; the blocked redirect was never requested.
        assert mock_get.call_count == 1

    def test_redirect_cap_raises(self, mock_get, _sleep, _guard):
        # Endless redirects → bounded and refused.
        mock_get.return_value = _redirect("https://example.com/loop")
        with pytest.raises(UnsafeUrlError, match="Too many redirects"):
            fetch_page_html("https://example.com")
        assert mock_get.call_count == _MAX_REDIRECTS + 1

    def test_relative_redirect_is_resolved_against_current_url(self, mock_get, _sleep, mock_guard):
        mock_get.side_effect = [_redirect("/elsewhere"), _ok("dest")]
        assert fetch_page_html("https://example.com/start") == "dest"
        # Relative Location resolved against the current URL before re-validation.
        assert mock_guard.call_args_list[1].args[0] == "https://example.com/elsewhere"
