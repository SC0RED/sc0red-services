"""Tests for the SSRF guard (assert_public_url)."""

import socket
from unittest.mock import patch

import pytest

from src.data_strategies.url_safety import UnsafeUrlError, assert_public_url

_GETADDRINFO = "src.data_strategies.url_safety.socket.getaddrinfo"


def _addrinfo(*ips: str):
    """Build a getaddrinfo-style return value for the given IPs (v4 or v6)."""
    infos = []
    for ip in ips:
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        sockaddr = (ip, 0, 0, 0) if family == socket.AF_INET6 else (ip, 0)
        infos.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr))
    return infos


class TestSchemeAndHost:
    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://host/x", "gopher://h/"])
    def test_non_http_scheme_rejected(self, url):
        with pytest.raises(UnsafeUrlError, match="scheme"):
            assert_public_url(url)

    def test_missing_host_rejected(self):
        with pytest.raises(UnsafeUrlError, match="no host"):
            assert_public_url("http://")

    def test_malformed_port_rejected_as_unsafe_url_error(self):
        # A bad port raises a plain ValueError from urlparse.port; the guard must
        # normalise it to UnsafeUrlError so fail-soft handlers catch it.
        with pytest.raises(UnsafeUrlError, match="invalid port"):
            assert_public_url("https://example.com:notaport")


class TestBlockedAddresses:
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",  # loopback
            "10.0.0.5",  # private
            "172.16.0.1",  # private
            "192.168.1.1",  # private
            "169.254.169.254",  # link-local / cloud metadata
            "0.0.0.0",  # unspecified  # noqa: S104
            "224.0.0.1",  # multicast
            "::1",  # IPv6 loopback
            "fe80::1",  # IPv6 link-local
            "fc00::1",  # IPv6 unique-local (private)
            "::ffff:169.254.169.254",  # IPv4-mapped IPv6 of metadata IP
        ],
    )
    def test_blocked_when_host_resolves_to_non_public(self, ip):
        with (
            patch(_GETADDRINFO, return_value=_addrinfo(ip)),
            pytest.raises(UnsafeUrlError, match="non-public"),
        ):
            assert_public_url("https://attacker.example")

    def test_blocked_if_any_record_is_private(self):
        # Host advertises a public AND a private address — must be refused.
        with (
            patch(_GETADDRINFO, return_value=_addrinfo("93.184.216.34", "10.0.0.1")),
            pytest.raises(UnsafeUrlError, match="non-public"),
        ):
            assert_public_url("https://dual.example")

    def test_literal_metadata_ip_rejected(self):
        with (
            patch(_GETADDRINFO, return_value=_addrinfo("169.254.169.254")),
            pytest.raises(UnsafeUrlError),
        ):
            assert_public_url("http://169.254.169.254/latest/meta-data/")

    def test_unresolvable_host_rejected(self):
        with (
            patch(_GETADDRINFO, side_effect=socket.gaierror("nodename nor servname")),
            pytest.raises(UnsafeUrlError, match="resolve"),
        ):
            assert_public_url("https://does-not-exist.example")


class TestPublicAllowed:
    def test_public_host_passes(self):
        with patch(_GETADDRINFO, return_value=_addrinfo("93.184.216.34")):
            assert_public_url("https://example.com")  # no raise

    def test_public_ipv6_passes(self):
        with patch(_GETADDRINFO, return_value=_addrinfo("2606:2800:220:1:248:1893:25c8:1946")):
            assert_public_url("https://example.com")  # no raise


class TestEscapeHatch:
    def test_private_allowed_when_env_set(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_ALLOW_PRIVATE_HOSTS", "true")
        # getaddrinfo must not even be consulted when the hatch is open.
        with patch(_GETADDRINFO, side_effect=AssertionError("should not resolve")):
            assert_public_url("http://ai-mock:8080/company")  # no raise

    def test_env_still_rejects_bad_scheme(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_ALLOW_PRIVATE_HOSTS", "true")
        with pytest.raises(UnsafeUrlError, match="scheme"):
            assert_public_url("file:///etc/passwd")

    def test_falsey_env_does_not_open_hatch(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_ALLOW_PRIVATE_HOSTS", "false")
        with (
            patch(_GETADDRINFO, return_value=_addrinfo("127.0.0.1")),
            pytest.raises(UnsafeUrlError),
        ):
            assert_public_url("http://localhost")
