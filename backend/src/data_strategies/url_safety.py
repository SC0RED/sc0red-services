"""SSRF guard for server-side URL fetches.

Every server-side scrape funnels through ``scraper_transport.fetch_page_html``,
which fetches whatever URL it's handed. Customers control those URLs (scan-start,
provide-a-source-url), so without a guard the worker could be coerced into
requesting internal hosts — cloud metadata (``169.254.169.254``), ``localhost``,
private ranges. ``assert_public_url`` is the single gate the transport runs
before every request (and every redirect hop).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Truthy → skip the IP-range checks (scheme/host checks still apply). Off by
# default so production Lambda is guarded with no extra config; set only in the
# E2E / local docker stacks, which scrape an internal ``ai-mock`` host.
_ALLOW_PRIVATE_HOSTS_ENVIRONMENT = "SCRAPER_ALLOW_PRIVATE_HOSTS"
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})


class UnsafeUrlError(ValueError):
    """A URL was rejected before fetching it (SSRF guard).

    Subclasses ``ValueError`` so it rides the existing fail-fast paths — the
    worker's ``except (EngineError, ValueError, RuntimeError)`` records a clean
    scan failure rather than letting it surface as an unhandled 500.
    """


def _private_hosts_allowed() -> bool:  # noqa: NAMING001  private predicate; env opt-out
    return os.environ.get(_ALLOW_PRIVATE_HOSTS_ENVIRONMENT, "").strip().lower() in _TRUTHY


def _is_blocked_address(  # noqa: NAMING001  is_-prefixed predicate (checker counts the leading _)
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    """Return True for any non-public address we must refuse to fetch."""
    # IPv4-mapped IPv6 (``::ffff:a.b.c.d``) would otherwise dodge the v4 checks.
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_public_url(url: str) -> None:  # noqa: NAMING001  assert is the verb (pytest-style)
    """Raise ``UnsafeUrlError`` unless ``url`` is a public http(s) resource.

    Resolves the host over every A/AAAA record and rejects the URL if any
    record is a private/loopback/link-local/multicast/reserved/unspecified
    address — checking all records blocks a host that advertises both a public
    and a private address. The IP checks are skipped when
    ``SCRAPER_ALLOW_PRIVATE_HOSTS`` is set (test/local stacks); the scheme and
    host checks always apply.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        message = f"Only http(s) URLs may be fetched, got scheme '{parsed.scheme}'"
        raise UnsafeUrlError(message)
    host = parsed.hostname
    if not host:
        message = f"URL has no host: '{url}'"
        raise UnsafeUrlError(message)

    if _private_hosts_allowed():
        return

    # ``parsed.port`` raises a plain ValueError on a malformed/out-of-range port
    # (e.g. 'https://x:abc'); normalise it to UnsafeUrlError so it rides the same
    # fail-soft handlers as every other refusal rather than escaping as a bare
    # ValueError.
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        message = f"URL has an invalid port: '{url}'"
        raise UnsafeUrlError(message) from error
    try:
        address_infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        message = f"Could not resolve host '{host}'"
        raise UnsafeUrlError(message) from error

    # getaddrinfo may return scoped IPv6 ('fe80::1%eth0'); strip the zone id.
    # ``str(...)`` pins the loosely-typed sockaddr element to a string.
    resolved = {str(info[4][0]).split("%")[0] for info in address_infos}
    if not resolved:
        message = f"Could not resolve host '{host}'"
        raise UnsafeUrlError(message)

    for ip_text in resolved:
        ip = ipaddress.ip_address(ip_text)
        if _is_blocked_address(ip):
            message = f"Refusing to fetch '{host}' — resolves to non-public address {ip_text}"
            raise UnsafeUrlError(message)
