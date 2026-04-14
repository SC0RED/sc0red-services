"""Portfolio company discovery step.

Runs two parallel discovery paths:
1. Heuristic: scrape + filter links with context-aware CTA handling
2. AI extraction: send page text to LLM for structured company extraction

Results merged: intersection auto-included, remainder passed to validation.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from signalfield_core.pipeline.step import RequestStep

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy
from src.data_strategies.web_scraper_strategy import scrape_url
from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call
from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

_PORTFOLIO_PATHS = [
    "",
    "/portfolio",
    "/companies",
    "/investments",
    "/portfolio-companies",
    "/our-companies",
]


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
) -> list[dict[str, str]]:
    """Merge heuristic and AI results by URL domain.

    Intersection (both paths) comes first, then remainder from either path.
    Deduplicates by normalized domain.
    """
    heuristic_by_domain = {_normalize_domain(c["url"]): c for c in heuristic}
    ai_by_domain = {_normalize_domain(c["url"]): c for c in ai_extracted}

    intersection = set(heuristic_by_domain) & set(ai_by_domain)
    all_domains = set(heuristic_by_domain) | set(ai_by_domain)

    # Intersection first (high confidence), then remainder
    merged = [heuristic_by_domain[d] for d in intersection]
    merged.extend(
        (heuristic_by_domain if d in heuristic_by_domain else ai_by_domain)[d]
        for d in all_domains - intersection
    )

    logger.info(
        "Merge: heuristic=%d, ai=%d, intersection=%d, total=%d",
        len(heuristic),
        len(ai_extracted),
        len(intersection),
        len(merged),
    )
    return merged


class DiscoverPortfolio(RequestStep):
    """Discovers portfolio companies using parallel heuristic + AI paths."""

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

        # Path 1: Heuristic discovery (improved with context-aware CTA)
        strategy = PortfolioDiscoveryStrategy({"url": url})
        _raw, metadata = strategy.execute()
        heuristic_companies = metadata.get("companies", [])

        # Path 2: AI extraction from scraped page text
        ai_companies: list[dict[str, str]] = []
        diagnostic = ""

        if self._ai_client_factory:
            page_text, page_links = self._scrape_for_ai(url)
            if page_text:
                ai_result = self._run_ai_extraction(url, page_text, page_links)
                ai_companies = ai_result.get("companies", [])
                if not ai_result.get("is_pe_firm", True):
                    diagnostic = ai_result.get(
                        "firm_type_description",
                        "This does not appear to be a PE/VC firm.",
                    )

        # Merge
        if heuristic_companies or ai_companies:
            companies = _merge_results(heuristic_companies, ai_companies)
        else:
            companies = []
            if not diagnostic:
                diagnostic = "Could not identify portfolio companies from this website."

        logger.info(
            "Discovered %d companies from %s (heuristic=%d, ai=%d)",
            len(companies),
            url,
            len(heuristic_companies),
            len(ai_companies),
        )

        self.request_executor.add_details(
            {
                "portfolio_companies": companies,
                "portfolio_companies_json": json.dumps(companies),
                "portfolio_count": len(companies),
                "portfolio_diagnostic": diagnostic,
            }
        )
        self.request_executor.mark_question_complete("discover_portfolio")

    def _scrape_for_ai(self, firm_url: str) -> tuple[str, list[dict[str, str]]]:
        """Scrape portfolio pages for AI analysis."""
        if not firm_url.startswith("http"):
            firm_url = f"https://{firm_url}"
        parsed = urlparse(firm_url)
        base_origin = f"{parsed.scheme}://{parsed.netloc}"

        text_parts: list[str] = []
        all_links: list[dict[str, str]] = []
        for path in _PORTFOLIO_PATHS:
            page_url = firm_url if not path else f"{base_origin}{path}"
            try:
                result = scrape_url(page_url)
                text_parts.append(result["text"])
                all_links.extend(result["links"])
            except Exception:
                logger.info("Skipping path %s (scrape error)", page_url)
                continue
        return "\n\n".join(text_parts), all_links

    def _run_ai_extraction(
        self,
        firm_url: str,
        page_text: str,
        links: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send page text to AI for structured company extraction."""
        links_text = "\n".join(
            f"- {link.get('text', '')}: {link.get('href', '')}" for link in links[:100]
        )
        template = load_template("extract_portfolio_companies")
        schema = load_schema("extract_portfolio_companies")
        system_prompt = load_system_prompt("portfolio_validation")

        prompt = template.format(
            firm_url=firm_url,
            page_text=page_text[:8000],
            links_text=links_text[:3000],
        )
        try:
            _label, result, _elapsed = run_structured_ai_call(
                ai_client_factory=self._ai_client_factory,
                user_prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                label="extract_portfolio",
                step_name="DiscoverPortfolio",
            )
        except Exception:
            logger.exception("AI portfolio extraction failed")
            return {"companies": [], "is_pe_firm": True}
        else:
            return result
