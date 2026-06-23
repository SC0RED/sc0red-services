"""Customer-triggered deepen step.

When the initial discovery returns an incomplete list for an opaque/CSR firm,
the customer can ask to "search deeper". This step runs a multi-pass, seeded
web search (``portfolio_websearch.run_deep_web_search_discovery``) and merges
the new candidates with the companies already on the scan.

The already-known companies are passed in as the seed and emitted as
``portfolio_auto_included`` (trusted — they survived the first round / were
customer-supplied), so the downstream ``ValidatePortfolioCompanies`` step only
validates the newly-recovered candidates. The structured verdict is rebuilt so
the confirmation screen reflects the augmented list and still offers to deepen
again or upload.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from signalfield_core.pipeline.step import RequestStep

from src.pipeline.pipeline_steps.portfolio_merge import build_verdict, find_new_candidates
from src.pipeline.pipeline_steps.portfolio_websearch import run_deep_web_search_discovery

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)


class DeepenPortfolio(RequestStep):
    """Recovers additional portfolio companies via a multi-pass web search."""

    def __init__(
        self,
        ai_client_factory: AIClientFactory | None = None,
        seed_companies: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory
        self._seed_companies = seed_companies or []

    def _require_ai_factory(self) -> AIClientFactory:
        """Return the AI client factory, failing fast if absent."""
        if self._ai_client_factory is None:
            message = "DeepenPortfolio requires an AI client factory"
            raise RuntimeError(message)
        return self._ai_client_factory

    def execute(self) -> None:
        """Run the deeper multi-pass search and merge with the existing list."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        url = accessor.company.url
        if not url:
            message = "No URL provided for portfolio deepen"
            raise ValueError(message)

        seed = self._seed_companies
        seed_names = [company["name"] for company in seed if company.get("name")]
        recovered = run_deep_web_search_discovery(
            self._require_ai_factory(), url, seed_names, step_name="DeepenPortfolio"
        )

        # Keep only candidates not already on the scan. Confidence-aware dedup
        # (shared with the initial fallback): the existing trusted list wins, so
        # a web-search find never repeats a company we already have and TLD
        # duplicates (acme.com / acme.in) collapse.
        fresh = find_new_candidates(recovered, seed)

        total = len(seed) + len(fresh)
        logger.info(
            "[DeepenPortfolio] %s: %d existing + %d new = %d candidates",
            url,
            len(seed),
            len(fresh),
            total,
        )

        # New (model-sourced) candidates need validation; the existing list is
        # trusted and skips it. ValidatePortfolioCompanies merges the two.
        # ``deepen_added`` lets the verdict report exhaustion: when a deepen round
        # adds nothing new, web search is tapped out → point the customer to upload.
        verdict = build_verdict(
            site_total=0,
            total=total,
            site_fetch_failed=False,
            fallback_ran=True,
            deepen_added=len(fresh),
        )
        self.request_executor.add_details(
            {
                "portfolio_companies": fresh,
                "portfolio_auto_included": seed,
                "portfolio_count": total,
                "discovery_verdict": verdict,
            }
        )
        self.request_executor.mark_question_complete("deepen_portfolio")
