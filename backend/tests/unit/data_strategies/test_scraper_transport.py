"""Tests for the browser-impersonating scrape transport + retry."""

from unittest.mock import MagicMock, patch

import pytest
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError

from src.data_strategies.scraper_transport import (
    _FETCH_MAX_ATTEMPTS,
    _IMPERSONATE_TARGET,
    _SCRAPER_TIMEOUT,
    fetch_page_html,
)


def _http_error(status_code: int) -> HTTPError:
    error = HTTPError(f"HTTP Error {status_code}")
    error.response = MagicMock(status_code=status_code)
    return error


def _ok(text: str = "<html><body>hi</body></html>") -> MagicMock:
    response = MagicMock()
    response.text = text
    response.raise_for_status = MagicMock()
    return response


@patch("src.data_strategies.scraper_transport.time.sleep")  # don't actually back off
@patch("src.data_strategies.scraper_transport.curl_requests.get")
class TestFetchPageHtml:
    def test_success_passes_impersonation_args(self, mock_get, _sleep):
        mock_get.return_value = _ok()
        html = fetch_page_html("https://example.com")
        assert html == "<html><body>hi</body></html>"
        _args, kwargs = mock_get.call_args
        assert kwargs["impersonate"] == _IMPERSONATE_TARGET
        assert kwargs["timeout"] == _SCRAPER_TIMEOUT
        assert kwargs["allow_redirects"] is True
        assert mock_get.call_count == 1  # no retry on success

    def test_retries_then_succeeds_on_transient_block(self, mock_get, _sleep):
        # First attempt 403 (Cloudflare challenge), second returns 200.
        blocked = MagicMock()
        blocked.raise_for_status.side_effect = _http_error(403)
        mock_get.side_effect = [blocked, _ok()]
        assert fetch_page_html("https://example.com") == "<html><body>hi</body></html>"
        assert mock_get.call_count == 2
        assert _sleep.call_count == 1  # one backoff between the two attempts

    def test_not_found_is_not_retried(self, mock_get, _sleep):
        nf = MagicMock()
        nf.raise_for_status.side_effect = _http_error(404)
        mock_get.return_value = nf
        with pytest.raises(HTTPError):
            fetch_page_html("https://example.com")
        assert mock_get.call_count == 1  # 404 → no retry

    def test_persistent_block_raises_after_max_attempts(self, mock_get, _sleep):
        blocked = MagicMock()
        blocked.raise_for_status.side_effect = _http_error(403)
        mock_get.return_value = blocked
        with pytest.raises(HTTPError):
            fetch_page_html("https://example.com")
        assert mock_get.call_count == _FETCH_MAX_ATTEMPTS
        assert _sleep.call_count == _FETCH_MAX_ATTEMPTS - 1  # no backoff after the last attempt

    def test_connection_error_is_retried(self, mock_get, _sleep):
        mock_get.side_effect = [CurlConnectionError("boom"), _ok()]
        assert fetch_page_html("https://example.com") == "<html><body>hi</body></html>"
        assert mock_get.call_count == 2

    def test_impersonate_error_not_retried(self, mock_get, _sleep):
        mock_get.side_effect = ImpersonateError("bad target")
        with pytest.raises(ImpersonateError):
            fetch_page_html("https://example.com")
        assert mock_get.call_count == 1  # programming error → propagate immediately
