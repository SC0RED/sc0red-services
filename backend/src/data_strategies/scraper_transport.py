"""Browser-impersonating HTTP transport for scraping, with retry.

Uses ``curl_cffi`` (libcurl + BoringSSL) to present a real-browser TLS/HTTP-2
fingerprint so Cloudflare JA3 bot management serves full content instead of a
403. Split from ``web_scraper_strategy`` so the transport (fetch + retry) is
separate from the BeautifulSoup parsing.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError, RequestException

from src.data_strategies.url_safety import UnsafeUrlError, assert_public_url

logger = logging.getLogger(__name__)

# Browser fingerprint to impersonate. MAINTENANCE: stale targets (e.g.
# chrome120/124) get blocked — keep curl_cffi fresh and bump this. Impersonation
# also sets a browser-consistent header set, so we add no custom headers.
_IMPERSONATE_TARGET = "chrome136"
_SCRAPER_TIMEOUT = 15.0

# Retry transient blocks/timeouts: a Lambda datacenter IP gets challenged by
# Cloudflare intermittently even with a browser fingerprint, and a large page can
# graze the timeout. Most blips clear on a second attempt. 404/410 are genuine
# (not retried); a misconfigured impersonation target is a bug (not retried).
_FETCH_MAX_ATTEMPTS = 3
_FETCH_RETRY_BACKOFF = 1.5  # seconds, linear (x attempt)
_RETRYABLE_STATUS = frozenset({403, 408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524})
# Cap manual redirect following. We follow redirects ourselves (rather than
# letting libcurl auto-follow) so each hop passes the SSRF guard — an allowed
# host must not 30x-redirect into a private/metadata address.
_MAX_REDIRECTS = 5
_REDIRECT_STATUS = range(300, 400)


def fetch_page_html(url: str) -> str:
    """GET a URL via the impersonating transport and return its HTML.

    The target URL — and every redirect hop — is validated by
    ``assert_public_url`` first, so a customer-supplied URL cannot coerce a fetch
    of an internal/private host (SSRF). Redirects are followed manually (up to
    ``_MAX_REDIRECTS``) for that reason. Each hop's request is retried on
    transient/blocked responses via ``_fetch_once``. Raises ``UnsafeUrlError``
    for a blocked target/redirect or too many redirects; otherwise propagates the
    transport errors ``_fetch_once`` raises.
    """
    current_url = url
    for _hop in range(_MAX_REDIRECTS + 1):
        assert_public_url(current_url)
        response = _fetch_once(current_url)
        if response.status_code in _REDIRECT_STATUS:
            location = response.headers.get("location")
            if not location:
                return response.text  # 3xx without a target — treat as terminal
            current_url = urljoin(current_url, location)
            continue
        return response.text
    message = f"Too many redirects (>{_MAX_REDIRECTS}) while fetching {url}"
    raise UnsafeUrlError(message)


def _fetch_once(url: str) -> Any:
    """GET a single (already-validated) URL with retry, without following redirects.

    Returns the ``curl_cffi`` response (which may be a 3xx the caller follows
    manually). Retries transient/blocked responses up to ``_FETCH_MAX_ATTEMPTS``
    with brief backoff; raises immediately on a non-retryable status (e.g.
    404/410) or a misconfigured impersonation target; raises the last error after
    exhausting retries.
    """
    last_error: RequestException | None = None
    for attempt in range(_FETCH_MAX_ATTEMPTS):
        try:
            response = curl_requests.get(
                url,
                impersonate=_IMPERSONATE_TARGET,
                timeout=_SCRAPER_TIMEOUT,
                allow_redirects=False,
            )
            response.raise_for_status()
        except ImpersonateError:
            raise  # misconfigured _IMPERSONATE_TARGET — a bug, never retry
        except HTTPError as error:
            if getattr(error.response, "status_code", None) not in _RETRYABLE_STATUS:
                raise  # genuine (404/410/…) — not transient
            last_error = error
        except RequestException as error:
            last_error = error  # connection / timeout — transient
        else:
            return response
        if attempt + 1 < _FETCH_MAX_ATTEMPTS:
            logger.info(
                "Scrape attempt %d/%d failed for %s (%s); retrying",
                attempt + 1,
                _FETCH_MAX_ATTEMPTS,
                url,
                type(last_error).__name__,
            )
            time.sleep(_FETCH_RETRY_BACKOFF * (attempt + 1))
    raise last_error  # type: ignore[misc]  # set on every non-returning iteration
