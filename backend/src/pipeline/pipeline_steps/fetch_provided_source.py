"""Customer-provided reliable-source step.

When discovery missed the right page (e.g. the firm's portfolio lives at a URL
we didn't reach), the customer can paste the URL of a page that lists the
companies. This step fetches THAT page server-side and runs the same trusted
scrape + extraction as ``DiscoverPortfolio`` — producing high-confidence
``provided_url`` candidates merged into the scan's existing list. Unlike "search
deeper", it never falls back to web search, so the result stays reliable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.pipeline.step import RequestStep

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy
from src.pipeline.pipeline_steps.portfolio_extract import extract_companies_from_scrape
from src.pipeline.pipeline_steps.portfolio_merge import (
    build_verdict,
    find_new_candidates,
    merge_results,
    sanitize_candidates,
)

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)


class FetchProvidedSource(RequestStep):
    """Scrape a customer-provided URL and merge its companies into the scan."""

    def __init__(
        self,
        ai_client_factory: AIClientFactory | None = None,
        seed_companies: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory
        self._seed_companies = seed_companies or []

    def _require_ai_factory(self) -> AIClientFactory:
        if self._ai_client_factory is None:
            message = "FetchProvidedSource requires an AI client factory"
            raise RuntimeError(message)
        return self._ai_client_factory

    def execute(self) -> None:
        """Scrape the provided URL, extract companies, merge with the seed."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        url = accessor.company.url
        if not url:
            message = "No URL provided for source fetch"
            raise ValueError(message)

        # Same scrape + extraction as DiscoverPortfolio, but on the customer's
        # page and with NO web-search fallback — provided_url stays reliable.
        _raw, metadata = PortfolioDiscoveryStrategy({"url": url}).execute()
        heuristic_companies = metadata["companies"]
        ai_companies: list[dict[str, str]] = []
        if self._ai_client_factory:
            page_text = metadata.get("page_text", "")
            script_text = metadata.get("script_text", "")
            if page_text or script_text:
                result = extract_companies_from_scrape(
                    self._require_ai_factory(),
                    url,
                    page_text,
                    script_text,
                    metadata.get("all_links", []),
                    step_name="FetchProvidedSource",
                )
                ai_companies = result.get("companies", [])

        if heuristic_companies or ai_companies:
            auto_included, needs_validation = merge_results(heuristic_companies, ai_companies)
        else:
            auto_included, needs_validation = [], []
        from_page = sanitize_candidates([*auto_included, *needs_validation])

        # Merge into the existing list (trusted-wins dedup); tag as provided_url.
        seed = self._seed_companies
        fresh = find_new_candidates(from_page, seed, source="provided_url")
        total = len(seed) + len(fresh)
        logger.info(
            "[FetchProvidedSource] %s: page yielded %d, %d new (existing=%d)",
            url,
            len(from_page),
            len(fresh),
            len(seed),
        )

        details: dict[str, Any] = {
            "portfolio_companies": fresh,
            "portfolio_auto_included": seed,
            "portfolio_count": total,
        }
        # Only assert a verdict when the provided page actually contributed
        # companies. All such candidates are reliable (seed + provided_url), so
        # site_total=total → partial_site_list (we still can't guarantee
        # completeness) anchored to the provided page. If the page added nothing
        # new, leave the scan's existing verdict untouched rather than relabelling
        # the unchanged list as site-derived — its prior provenance (e.g.
        # web_search_subset) stays honest.
        if fresh:
            details["discovery_verdict"] = build_verdict(
                site_total=total,
                total=total,
                site_fetch_failed=False,
                fallback_ran=False,
                site_source_url=url,
            )
        self.request_executor.add_details(details)
        self.request_executor.mark_question_complete("fetch_provided_source")
