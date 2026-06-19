"""Browser-impersonating HTTP transport for scraping, with retry.

Uses ``curl_cffi`` (libcurl + BoringSSL) to present a real-browser TLS/HTTP-2
fingerprint so Cloudflare JA3 bot management serves full content instead of a
403. Split from ``web_scraper_strategy`` so the transport (fetch + retry) is
separate from the BeautifulSoup parsing.
"""

from __future__ import annotations

import logging
import time

from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import HTTPError, ImpersonateError, RequestException

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


def fetch_page_html(url: str) -> str:
    """GET a URL via the impersonating transport and return its HTML.

    Retries transient/blocked responses (retryable HTTP status, connection,
    timeout) up to ``_FETCH_MAX_ATTEMPTS`` with brief backoff. Raises immediately
    on a non-retryable status (e.g. 404/410) or a misconfigured impersonation
    target; raises the last error after exhausting retries. Callers translate the
    raised ``curl_cffi`` errors into their existing error contracts.
    """
    last_error: RequestException | None = None
    for attempt in range(_FETCH_MAX_ATTEMPTS):
        try:
            response = curl_requests.get(
                url,
                impersonate=_IMPERSONATE_TARGET,
                timeout=_SCRAPER_TIMEOUT,
                allow_redirects=True,
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
            return response.text
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
