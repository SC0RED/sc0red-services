"""Portfolio company discovery step.

Runs two sequential discovery paths on the same scraped data:
1. Heuristic: scrape + filter links with context-aware CTA handling
2. AI extraction: send page text to LLM for structured company extraction

Results merged by URL domain: intersection auto-included, remainder passed
to downstream validation step.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from signalfield_core.pipeline.step import RequestStep

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy
from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call
from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)


def _normalize_domain(url: str) -> str:
    """Normalize URL to domain for matching (strip www., trailing slash)."""
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    domain = (parsed.netloc or "").lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _merge_results(
    heuristic: list[dict[str, str]],
    ai_extracted: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Merge heuristic and AI results by URL domain.

    Returns ``(auto_included, needs_validation)``:
    - ``auto_included``: companies found by BOTH paths (high confidence, skip AI validation)
    - ``needs_validation``: companies found by only one path (require AI validation)

    Deduplicates by normalized domain.
    """
    heuristic_by_domain = {_normalize_domain(c["url"]): c for c in heuristic}
    ai_by_domain = {_normalize_domain(c["url"]): c for c in ai_extracted}

    intersection = set(heuristic_by_domain) & set(ai_by_domain)
    remainder_domains = (set(heuristic_by_domain) | set(ai_by_domain)) - intersection

    auto_included = [heuristic_by_domain[d] for d in intersection]
    needs_validation = [
        (heuristic_by_domain if d in heuristic_by_domain else ai_by_domain)[d]
        for d in remainder_domains
    ]

    logger.info(
        "Merge: heuristic=%d, ai=%d, intersection=%d, remainder=%d, total=%d",
        len(heuristic),
        len(ai_extracted),
        len(intersection),
        len(needs_validation),
        len(auto_included) + len(needs_validation),
    )
    return auto_included, needs_validation


class DiscoverPortfolio(RequestStep):
    """Discovers portfolio companies using heuristic + AI extraction paths."""

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run heuristic + AI discovery and merge results."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        url = accessor.company.url

        if not url:
            message = "No URL provided for portfolio discovery"
            raise ValueError(message)

        # Path 1: Heuristic discovery (also captures page text + links)
        strategy = PortfolioDiscoveryStrategy({"url": url})
        _raw, metadata = strategy.execute()
        heuristic_companies = metadata["companies"]

        # Path 2: AI extraction reuses scraped data (no duplicate HTTP requests)
        ai_companies: list[dict[str, str]] = []
        diagnostic = ""

        if self._ai_client_factory:
            page_text = metadata.get("page_text", "")
            page_links = metadata.get("all_links", [])
            if page_text:
                ai_result = self._run_ai_extraction(url, page_text, page_links)
                ai_companies = ai_result.get("companies", [])
                if not ai_result.get("is_pe_firm", True):
                    diagnostic = ai_result.get(
                        "firm_type_description",
                        "This does not appear to be a PE/VC firm.",
                    )

        # Merge into auto-included (intersection, high confidence) and
        # needs-validation (remainder, only one path found it).
        if heuristic_companies or ai_companies:
            auto_included, needs_validation = _merge_results(
                heuristic_companies, ai_companies
            )
        else:
            auto_included, needs_validation = [], []
            if not diagnostic:
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

        # ``portfolio_companies`` carries only the remainder that needs AI
        # validation. ``portfolio_auto_included`` is merged back in by
        # ``ValidatePortfolioCompanies`` after validation completes.
        self.request_executor.add_details(
            {
                "portfolio_companies": needs_validation,
                "portfolio_auto_included": auto_included,
                "portfolio_companies_json": json.dumps(
                    auto_included + needs_validation
                ),
                "portfolio_count": total,
                "portfolio_diagnostic": diagnostic,
            }
        )
        self.request_executor.mark_question_complete("discover_portfolio")

    def _run_ai_extraction(
        self,
        firm_url: str,
        page_text: str,
        links: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send page text to AI for structured company extraction."""
        links_text = "\n".join(f"- {link['text']}: {link['href']}" for link in links[:100])
        template = load_template("extract_portfolio_companies")
        schema = load_schema("extract_portfolio_companies")
        system_prompt = load_system_prompt("portfolio_validation")

        prompt = template.format(
            firm_url=firm_url,
            page_text=page_text[:8000],
            links_text=links_text[:3000],
        )
        _label, result, _elapsed = run_structured_ai_call(
            ai_client_factory=self._ai_client_factory,
            user_prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            label="extract_portfolio",
            step_name="DiscoverPortfolio",
        )
        return result
