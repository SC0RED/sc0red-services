"""Tests for data-bearing <script> JSON extraction (resilient-portfolio-discovery).

SSR sites embed the portfolio company list as JSON inside a <script> tag while
the visible <body> is a skeleton. `_extract_data_scripts` must surface the dense
JSON island and skip code/analytics scripts.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from src.data_strategies.web_scraper_strategy import (
    _MAX_SCRIPT_TEXT_LENGTH,
    _extract_data_scripts,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_picks_dense_json_island_over_code_and_analytics():
    html = """
    <html><head>
      <script src="https://cdn/runtime.js"></script>
      <script>function track(){gtag('config','x');for(let i=0;i<10;i++){}}</script>
      <script>
        window.__DATA__ = '{"companies":[
          {"name":"Sophos","slug":"sophos","url":"https://sophos.com"},
          {"name":"Dynatrace","slug":"dynatrace","url":"https://dynatrace.com"},
          {"name":"Proofpoint","slug":"proofpoint","url":"https://proofpoint.com"}]}';
      </script>
    </head><body><div>skeleton</div></body></html>
    """
    out = _extract_data_scripts(_soup(html))
    assert "Sophos" in out and "Dynatrace" in out and "Proofpoint" in out
    # The analytics/code script (no JSON pairs) is not the signal; the island is.
    assert "gtag" not in out


def test_handles_escaped_json_islands():
    # Next.js-style stringified JSON: keys escaped as \"name\":\"...\".
    # Enough items to clear the JSON-pair threshold.
    items = (
        r"{\"name\":\"Acme\",\"slug\":\"acme\"},"
        r"{\"name\":\"Globex\",\"slug\":\"globex\"},"
        r"{\"name\":\"Initech\",\"slug\":\"initech\"}"
    )
    html = (
        '<html><head><script>self.__next_f.push([1,"{\\"items\\":['
        + items
        + ']}"])</script></head><body></body></html>'
    )
    out = _extract_data_scripts(_soup(html))
    assert "Acme" in out and "Globex" in out and "Initech" in out


def test_skips_external_and_empty_scripts():
    html = '<html><head><script src="https://x/app.js"></script><script></script></head><body></body></html>'
    assert _extract_data_scripts(_soup(html)) == ""


def test_respects_budget():
    big = '{"name":"X","v":"y"}' * 40_000  # well over the budget
    html = f"<html><head><script>{big}</script></head><body></body></html>"
    out = _extract_data_scripts(_soup(html))
    assert len(out) <= _MAX_SCRIPT_TEXT_LENGTH
