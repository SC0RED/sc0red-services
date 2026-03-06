"""Portfolio company discovery step.

Uses PortfolioDiscoveryStrategy to find companies from a PE firm's website.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from signalfield_core.pipeline.step import RequestStep

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy

if TYPE_CHECKING:
    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)


class DiscoverPortfolio(RequestStep):
    """Discovers portfolio companies from a PE firm's website URL."""

    def execute(self) -> None:
        """Discover portfolio companies from the PE firm URL and store results."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        # The URL is stored on the company accessor
        url = accessor.company.url

        if not url:
            message = "No URL provided for portfolio discovery"
            raise ValueError(message)

        strategy = PortfolioDiscoveryStrategy({"url": url})
        raw_json, metadata = strategy.execute()

        companies = metadata.get("companies", [])
        logger.info("Discovered %d portfolio companies from %s", len(companies), url)

        # Store discovered companies in execution details
        self.request_executor.add_details(
            {
                "portfolio_companies": companies,
                "portfolio_companies_json": raw_json,
                "portfolio_count": len(companies),
            }
        )

        self.request_executor.mark_question_complete("discover_portfolio")
