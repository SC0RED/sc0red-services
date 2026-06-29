"""Portfolio company discovery step.

Runs two sequential discovery paths on the same scraped data:
1. Heuristic: scrape + filter links with context-aware CTA handling
2. AI extraction: send page text to LLM for structured company extraction

Results merged by normalized URL key (host + path): intersection auto-included,
remainder passed to downstream validation step. When the site yields too few
companies, a web-search fallback recovers the portfolio. Merge/verdict logic
lives in ``portfolio_merge`` and the web-search calls in ``portfolio_websearch``
(both shared with the customer-triggered ``DeepenPortfolio`` step).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

from signalfield_core.pipeline.step import RequestStep

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy
from src.data_strategies.sitemap_strategy import discover_via_sitemap
from src.data_strategies.wp_json_strategy import discover_via_wp_json
from src.pipeline.pipeline_steps.delivery_mechanism import classify_delivery_mechanism
from src.pipeline.pipeline_steps.portfolio_extract import extract_companies_from_scrape
from src.pipeline.pipeline_steps.portfolio_merge import (
    build_verdict,
    find_new_candidates,
    merge_fallback,
    merge_results,
)
from src.pipeline.pipeline_steps.portfolio_names import sanitize_candidates
from src.pipeline.pipeline_steps.portfolio_websearch import run_web_search_discovery
from src.repositories.dynamodb.discovery_cache_repository import FAST_PATH_MIN_COUNT

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor
    from src.pipeline.request_executor import Sc0redServicesRequestExecutor
    from src.repositories.dynamodb.discovery_cache_repository import DiscoveryCacheRepository

logger = logging.getLogger(__name__)

# Background progress messages narrated to the customer as discovery climbs the
# ladder (Task 7 of adaptive-portfolio-discovery). Mechanism routing is never a
# customer choice — they only see transparency as progress. Percentages sit in
# the 5%→10% discovery window (5% start, 10% discover_portfolio complete) and
# rise monotonically so the bar never jumps backwards. Real-time only (AppSync);
# polling clients see the coarse phase boundaries.
_PHASE_READING = (6, "Reading the firm's portfolio page…")
_PHASE_STRUCTURED = (8, "Querying the firm's data sources…")
_PHASE_WEB_SEARCH = (9, "Searching public sources…")

# Low-water mark: when site-derived discovery finds this many companies OR FEWER,
# auto-run the web-search fallback to recover the firm's portfolio (the site is
# opaque / client-side-only / paginated / a thin logo grid). Set above 0 because
# a small non-zero scrape is almost always partial — e.g. dev verification saw
# Audax=4, Alpine=3 of much larger portfolios. Kept small so genuinely-small
# portfolios and clean full listings don't pay the web-search cost; everything
# above this relies on the always-available customer-triggered "Search deeper".
_FALLBACK_THRESHOLD = 5

# When the in-HTML paths (links + AI + embedded JSON) find this many companies OR
# FEWER, try the deterministic structured-source rungs (WordPress wp-json portfolio
# CPT + sitemap enumeration) before the web-search fallback. These are browser-free
# and authoritative — they rescue client-side-rendered shells the scrape can't see
# (the adaptive-portfolio-discovery spike: Vista/Insight/General Atlantic/Alpine/
# Kohlberg via wp-json, Riverside/Audax via sitemap). Same low-water mark as the
# web-search fallback: a firm whose site already yielded a real list doesn't need
# them, and they run before (and usually obviate) the costlier web search.
_DETERMINISTIC_RUNG_THRESHOLD = _FALLBACK_THRESHOLD


def _origin_of(url: str) -> str:
    """Scheme+host origin for the structured rungs (e.g. ``https://www.firm.com``)."""
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    return f"{parsed.scheme}://{parsed.netloc}"


class DiscoverPortfolio(RequestStep):
    """Discovers portfolio companies using heuristic + AI extraction paths."""

    def __init__(
        self,
        ai_client_factory: AIClientFactory | None = None,
        discovery_cache_repo: DiscoveryCacheRepository | None = None,
    ) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory
        self._discovery_cache_repo = discovery_cache_repo

    def _require_ai_factory(self) -> AIClientFactory:
        """Return the AI client factory, failing fast if absent.

        The AI extraction and web-search fallback both run only inside an
        ``if self._ai_client_factory`` guard in :meth:`execute`, so a missing
        factory here is a programming error — surface it loudly rather than
        passing ``None`` into the AI call.
        """
        if self._ai_client_factory is None:
            message = "DiscoverPortfolio requires an AI client factory for this path"
            raise RuntimeError(message)
        return self._ai_client_factory

    def _report_phase(self, phase: tuple[int, str]) -> None:
        """Narrate a discovery sub-phase on the scan's real-time progress channel."""
        executor = cast("Sc0redServicesRequestExecutor", self.request_executor)
        progress, label = phase
        executor.report_progress(progress, label)

    def _run_cached_rung(self, source: str, url: str) -> list[dict[str, str]]:
        """Run the single structured rung a prior scan proved serves this domain."""
        origin = _origin_of(url)
        if source == "wp_json":
            candidates = discover_via_wp_json(origin)
        elif source == "sitemap":
            candidates = discover_via_sitemap(origin)
        else:
            return []
        # source="site" matches the normal rung path; the fast-path verdict sets
        # site_source_url unconditionally, so every record anchors to the firm page.
        return find_new_candidates(sanitize_candidates(candidates), [], source="site")

    def _try_cached_fast_path(self, url: str) -> bool:  # noqa: NAMING001  returns "handled?", not an is_ predicate
        """Fast path: re-run the proven structured rung first; skip the rest on a hit.

        When a prior scan recorded that a deterministic rung (wp-json / sitemap)
        serves this domain, run just that rung. If it still yields a healthy list
        the firm's portfolio is read directly — no scrape, no AI extraction, no
        web search. Returns True when it handled the scan. Self-healing: a stale
        entry yields too few companies, so we return False and let the caller run
        full discovery (which re-records the cache).
        """
        if self._discovery_cache_repo is None:
            return False
        cached = self._discovery_cache_repo.get_proven_path(url)
        if not cached:
            return False
        self._report_phase(_PHASE_STRUCTURED)
        fast = self._run_cached_rung(cached["source"], url)
        if len(fast) <= FAST_PATH_MIN_COUNT:
            logger.info(
                "Discovery cache stale for %s (source=%s, got %d) — full rediscovery",
                url,
                cached["source"],
                len(fast),
            )
            return False
        logger.info(
            "Discovery cache hit for %s via %s (%d companies) — skipping scrape/AI/web-search",
            url,
            cached["source"],
            len(fast),
        )
        verdict = build_verdict(
            site_total=len(fast),
            total=len(fast),
            site_fetch_failed=False,
            fallback_ran=False,
            mechanism="structured_endpoint",
            site_source_url=url,
        )
        self.request_executor.add_details(
            {
                "portfolio_companies": fast,
                "portfolio_auto_included": [],
                "portfolio_companies_json": json.dumps(fast),
                "portfolio_count": len(fast),
                "portfolio_diagnostic": "",
                "discovery_verdict": verdict,
            }
        )
        # Refresh the TTL + count so an actively re-scanned firm stays cached.
        self._discovery_cache_repo.put_proven_path(
            url, source=cached["source"], count=len(fast), mechanism="structured_endpoint"
        )
        self.request_executor.mark_question_complete("discover_portfolio")
        return True

    def execute(self) -> None:
        """Run heuristic + AI discovery and merge results."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        url = accessor.company.url

        if not url:
            message = "No URL provided for portfolio discovery"
            raise ValueError(message)

        # A prior scan may have proved a deterministic structured rung serves this
        # domain — run it first and skip the costly full ladder when it still hits.
        if self._try_cached_fast_path(url):
            return

        # Path 1: Heuristic discovery (also captures page text + links)
        self._report_phase(_PHASE_READING)
        strategy = PortfolioDiscoveryStrategy({"url": url})
        _raw, metadata = strategy.execute()
        heuristic_companies = metadata["companies"]

        # Path 2: AI extraction reuses scraped data (no duplicate HTTP requests)
        ai_companies: list[dict[str, str]] = []
        diagnostic = ""
        is_pe_firm = True  # assume PE unless the extractor says otherwise

        if self._ai_client_factory:
            page_text = metadata.get("page_text", "")
            script_text = metadata.get("script_text", "")
            page_links = metadata.get("all_links", [])
            if page_text or script_text:
                ai_result = extract_companies_from_scrape(
                    self._require_ai_factory(),
                    url,
                    page_text,
                    script_text,
                    page_links,
                    step_name="DiscoverPortfolio",
                )
                ai_companies = ai_result.get("companies", [])
                is_pe_firm = ai_result.get("is_pe_firm", True)
                if not is_pe_firm:
                    diagnostic = ai_result.get(
                        "firm_type_description",
                        "This does not appear to be a PE/VC firm.",
                    )

        # Merge into auto-included (intersection, high confidence) and
        # needs-validation (remainder, only one path found it).
        if heuristic_companies or ai_companies:
            auto_included, needs_validation = merge_results(heuristic_companies, ai_companies)
        else:
            auto_included, needs_validation = [], []

        # Sanitize site results BEFORE counting/dedup so the fallback gate and the
        # web-search dedup work on clean names+URLs (a "View Site" row that
        # re-derives to a real company must dedup against the fallback correctly,
        # and login-junk shouldn't count toward site_total).
        auto_included = sanitize_candidates(auto_included)
        needs_validation = sanitize_candidates(needs_validation)

        # Deterministic structured-source rungs: when the in-HTML paths come up
        # thin, try the firm's own structured sources — a WordPress wp-json
        # portfolio CPT and sitemap enumeration — before paying for web search.
        # Both are browser-free and authoritative (and run even without an AI
        # factory). New candidates enter needs_validation only, so a wp-json CPT
        # that includes exited companies still gets AI-validated downstream.
        in_html_total = len(auto_included) + len(needs_validation)
        rung_count = 0  # companies the deterministic rungs contributed (for mechanism)
        proven_source = ""  # which rung carried the result (for the per-domain cache)
        if is_pe_firm and in_html_total <= _DETERMINISTIC_RUNG_THRESHOLD:
            self._report_phase(_PHASE_STRUCTURED)
            base_origin = _origin_of(url)
            # Run the rungs separately so we can attribute which one carried the
            # result — that's what the per-domain cache records to fast-path the
            # next re-scan. Sitemap dedups against wp-json's fresh hits.
            existing = [*auto_included, *needs_validation]
            wp_fresh = find_new_candidates(
                sanitize_candidates(discover_via_wp_json(base_origin)), existing, source="site"
            )
            sitemap_fresh = find_new_candidates(
                sanitize_candidates(discover_via_sitemap(base_origin)),
                [*existing, *wp_fresh],
                source="site",
            )
            fresh = [*wp_fresh, *sitemap_fresh]
            rung_count = len(fresh)
            if fresh:
                logger.info("Deterministic rungs added %d companies for %s", rung_count, url)
                needs_validation = [*needs_validation, *fresh]
            # Only cache a SINGLE-rung result. If both rungs carried distinct
            # companies, fast-pathing one of them on a re-scan would silently drop
            # the other's exclusive companies — so the mixed case is left
            # un-cached (proven_source ""), and re-scans run the full ladder.
            if wp_fresh and not sitemap_fresh:
                proven_source = "wp_json"
            elif sitemap_fresh and not wp_fresh:
                proven_source = "sitemap"

        # Site-first, fallback-on-low-yield: when the firm's own site yields too
        # few companies (opaque / client-side-only / non-embedding), recover the
        # portfolio via web search. Strictly additive — fallback candidates enter
        # the needs-validation tier only, never auto-included.
        site_total = len(auto_included) + len(needs_validation)
        fallback_ran = False
        if self._ai_client_factory and is_pe_firm and site_total <= _FALLBACK_THRESHOLD:
            fallback_ran = True
            self._report_phase(_PHASE_WEB_SEARCH)
            # Surface WHY we're falling back: a fetch failure means a scrapeable
            # site was unreachable this run (result may be incomplete), vs a
            # genuinely empty/opaque site where web search is the right recovery.
            if metadata.get("site_fetch_failed"):
                logger.warning(
                    "Site fetch failed for %s — falling back to web search; "
                    "result may be incomplete",
                    url,
                )
            else:
                logger.info("Site yielded no companies for %s — using web-search fallback", url)
            # Seed with on-site logo-grid names when present (e.g. Vista): the
            # site supplies the authoritative WHO, web search resolves the URLs.
            seed_names = metadata.get("logo_company_names", [])
            fallback = sanitize_candidates(
                run_web_search_discovery(
                    self._require_ai_factory(), url, seed_names, step_name="DiscoverPortfolio"
                )
            )
            needs_validation = merge_fallback(auto_included, needs_validation, fallback)

        if not (auto_included or needs_validation) and not diagnostic:
            diagnostic = "Could not identify portfolio companies from this website."

        total = len(auto_included) + len(needs_validation)
        logger.info(
            "Discovered %d companies from %s (heuristic=%d, ai=%d, "
            "auto_included=%d, needs_validation=%d)",
            total,
            url,
            len(heuristic_companies),
            len(ai_companies),
            len(auto_included),
            len(needs_validation),
        )

        # How the firm delivered its list — carried on the verdict so a thin/empty
        # result can be explained (CSR shell vs genuinely small) rather than guessed.
        # Sanitized counts so the mechanism is consistent with site_total (which
        # is post-sanitize): a firm whose anchors are all junk that sanitize drops
        # must not be labeled static_listing on an otherwise-empty result.
        mechanism = classify_delivery_mechanism(
            heuristic_count=len(sanitize_candidates(heuristic_companies)),
            ai_count=len(sanitize_candidates(ai_companies)),
            rung_count=rung_count,
            script_present=bool(metadata.get("script_text")),
            page_text_length=len(metadata.get("page_text", "")),
            site_fetch_failed=bool(metadata.get("site_fetch_failed")),
            site_total=site_total,
        )
        logger.info("Delivery mechanism for %s: %s", url, mechanism)

        # ``portfolio_companies`` carries only the remainder that needs AI
        # validation. ``portfolio_auto_included`` is merged back in by
        # ``ValidatePortfolioCompanies`` after validation completes.
        verdict = build_verdict(
            site_total=site_total,
            total=total,
            site_fetch_failed=bool(metadata.get("site_fetch_failed")),
            fallback_ran=fallback_ran,
            mechanism=mechanism,
            # The page we read — only meaningful when the site actually yielded
            # companies; the UI shows it as the reliable-source anchor.
            # Anchor to the page only if site-derived companies actually survived
            # sanitization (not just the pre-sanitize site_total).
            site_source_url=url
            if any(c.get("source") == "site" for c in (*auto_included, *needs_validation))
            else "",
        )
        self.request_executor.add_details(
            {
                "portfolio_companies": needs_validation,
                "portfolio_auto_included": auto_included,
                "portfolio_companies_json": json.dumps(auto_included + needs_validation),
                "portfolio_count": total,
                "portfolio_diagnostic": diagnostic,
                "discovery_verdict": verdict,
            }
        )
        # Record the proven structured rung so a re-scan of this domain fast-paths
        # straight to it. Only cache a substantial deterministic yield — a thin
        # rung result isn't a reliable fast path (put_proven_path also ignores
        # non-structured sources). No-op without a cache repo (local dev / tests).
        if (
            self._discovery_cache_repo is not None
            and proven_source
            and rung_count > FAST_PATH_MIN_COUNT
        ):
            self._discovery_cache_repo.put_proven_path(
                url, source=proven_source, count=rung_count, mechanism=mechanism
            )
        self.request_executor.mark_question_complete("discover_portfolio")
