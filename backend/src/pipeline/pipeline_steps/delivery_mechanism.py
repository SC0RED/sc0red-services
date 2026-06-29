"""Classify how a firm delivered its portfolio, from the discovery outcome.

A *post-discovery* label (for telemetry + customer messaging), describing WHICH
source actually produced the list — not a pre-fetch router. The discovery verdict
carries it so a thin/empty result can be explained ("renders client-side, we
couldn't read it" vs "genuinely small server-rendered list") instead of guessed
at. See openspec/changes/adaptive-portfolio-discovery/design.md.

Derived from which discovery paths bore fruit (deterministic, no extra fetches):
attribution is more reliable than re-parsing HTML signatures, because we already
know what each path returned.
"""

from __future__ import annotations

# Heuristic-anchor count above which we're confident the firm server-renders its
# whole list (vs a handful of stray anchors on an otherwise client-side shell —
# e.g. Audax's ~5 "View Case Study" links).
_SUBSTANTIAL_LISTING = 5
# Visible-text length below which a zero-result page reads as a client-side shell
# (the DOM is a skeleton painted by JS) rather than a real page with no portfolio.
_SHELL_TEXT_LENGTH = 1500


def classify_delivery_mechanism(
    *,
    heuristic_count: int,
    ai_count: int,
    rung_count: int,
    script_present: bool,
    page_text_length: int,
    site_fetch_failed: bool,
    site_total: int,
) -> str:
    """Label the delivery mechanism behind a discovery result.

    Returns one of: ``unreachable`` (fetch blocked/failed), ``static_listing``
    (server-rendered anchors), ``structured_endpoint`` (wp-json / sitemap rung),
    ``embedded_json`` (AI read an inline ``<script>`` payload), ``ai_extracted``
    (AI read visible text), ``opaque_shell`` (nothing found + skeletal DOM ⇒
    likely client-side-rendered and unread), ``no_portfolio_found`` (nothing
    found on a substantive page), or ``site_listing`` (a defensive catch-all for
    a non-zero result with no clear path attribution — not produced by the
    current discovery flow, where a non-zero ``site_total`` implies one of the
    counts above is non-zero, but kept so the classifier is total over its inputs).
    """
    if site_fetch_failed and site_total == 0:
        return "unreachable"
    if heuristic_count > _SUBSTANTIAL_LISTING:
        return "static_listing"
    if rung_count > 0:
        return "structured_endpoint"
    if ai_count > 0:
        return "embedded_json" if script_present else "ai_extracted"
    if heuristic_count > 0:
        return "static_listing"  # small but server-rendered
    if site_total == 0:
        return "opaque_shell" if page_text_length < _SHELL_TEXT_LENGTH else "no_portfolio_found"
    return "site_listing"
