#!/usr/bin/env python3
"""Live verification harness for the adaptive-portfolio-discovery rungs.

Runs the deterministic discovery rungs (WordPress ``wp-json`` CPT + ``sitemap``
enumeration) against the 19 real PE/VC firms from the Task-0 spike that prioritised
the approach. This is a MANUAL tool — it hits external sites, so it is NOT a CI
gate (kept out of ``tests/`` deliberately). Run it after changing the rungs to
confirm real-world behaviour:

    uv run python scripts/verify_discovery_corpus.py

Each firm should resolve to a sane portfolio via at least one rung (or be a known
in-HTML/server-rendered case the rungs intentionally skip — those are marked
``in_html`` and verified by the scrape path, not here).
"""

from __future__ import annotations

import sys

from src.data_strategies.sitemap_strategy import discover_via_sitemap
from src.data_strategies.wp_json_strategy import discover_via_wp_json

# firm, base_origin, expected primary mechanism (from the spike — see
# openspec/changes/adaptive-portfolio-discovery/design.md).
CORPUS: list[tuple[str, str, str]] = [
    ("Thoma Bravo", "https://www.thomabravo.com", "in_html (RSC)"),
    ("Vista", "https://www.vistaequitypartners.com", "wp-json company"),
    ("Silver Lake", "https://www.silverlake.com", "anchors + wp-json portfolio"),
    ("Warburg Pincus", "https://warburgpincus.com", "in_html (anchors)"),
    ("Francisco Partners", "https://www.franciscopartners.com", "in_html (Nuxt anchors)"),
    ("Insight Partners", "https://www.insightpartners.com", "wp-json sfcompany"),
    ("General Atlantic", "https://www.generalatlantic.com", "wp-json investment"),
    ("Summit Partners", "https://www.summitpartners.com", "in_html (anchors)"),
    ("Alpine Investors", "https://alpineinvestors.com", "wp-json our-companies"),
    ("Riverside", "https://www.riversidecompany.com", "sitemap"),
    ("Audax", "https://www.audaxprivateequity.com", "sitemap"),
    ("Shore Capital", "https://www.shorecp.com", "in_html / wp-json"),
    ("Webster Equity", "https://websterequity.com", "blocked on plain curl"),
    ("Gryphon", "https://www.gryphon-inv.com", "wp-json companies"),
    ("Trivest", "https://www.trivest.com", "in_html (data-fields)"),
    ("Wind Point", "https://www.windpointpartners.com", "blocked on plain curl"),
    ("Halifax", "https://thehalifaxgroup.com", "in_html (cards)"),
    ("Sun Capital", "https://suncappart.com", "wp-json post_portfolio"),
    ("Kohlberg", "https://www.kohlberg.com", "wp-json company"),
]


def main() -> int:
    print(f"{'Firm':<20} {'wp-json':>8} {'sitemap':>8}  expected / sample")
    print("-" * 96)
    for firm, base, expected in CORPUS:
        try:
            wp = discover_via_wp_json(base)
        except Exception as error:
            wp = []
            print(f"{firm:<20} {'ERR':>8} {'':>8}  wp-json raised: {error!r}")
        sm = discover_via_sitemap(base)
        sample = next((c["name"] for c in (*wp, *sm)), "")
        print(f"{firm:<20} {len(wp):>8} {len(sm):>8}  {expected}  | {sample}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
