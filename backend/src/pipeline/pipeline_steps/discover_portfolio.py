"""Portfolio company discovery step.

Uses PortfolioDiscoveryStrategy to find companies from a PE firm's website.
"""

from __future__ import annotations

import logging

from signalfield_core.pipeline.step import RequestStep

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy

logger = logging.getLogger(__name__)


class DiscoverPortfolio(RequestStep):
    """Discovers portfolio companies from a PE firm's website URL."""

    def execute(self) -> None:
        """Discover portfolio companies from the PE firm URL and store results."""
        accessor = self.entity_accessor
        # The URL is stored on the company accessor
        url = ""
        if hasattr(accessor, "company"):
            url = accessor.company.url  # type: ignore[union-attr]

        if not url:
            msg = "No URL provided for portfolio discovery"
            raise ValueError(msg)

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
