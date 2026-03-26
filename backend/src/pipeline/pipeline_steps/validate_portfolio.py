"""Pipeline step: validate discovered portfolio companies with AI.

Uses parallel AI calls via FutureManager to confirm each discovered URL
is genuinely a portfolio company (not a firm page, nav link, or tool).
Fail-open: companies whose validation call errors are kept.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManager

from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call
from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

_MAX_WORKERS = 10


class ValidatePortfolioCompanies(RequestStep):
    """Validates discovered portfolio companies via parallel AI calls.

    Each company is checked against the firm URL to confirm it is a real
    portfolio investment rather than a navigation link or firm page.
    On AI error for an individual company, the company is kept (fail-open).
    """

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Validate each discovered company and filter non-portfolio entries."""
        companies: list[dict[str, Any]] = self.request_executor.details.get(
            "portfolio_companies", []
        )

        if not companies or not self._ai_client_factory:
            self.request_executor.mark_question_complete("validate_portfolio")
            return

        accessor = cast("CompanyAccessor", self.entity_accessor)
        firm_url = accessor.company.url

        system_prompt = load_system_prompt("portfolio_validation")
        template = load_template("portfolio_validation")
        schema = load_schema("portfolio_validation")

        worker_count = min(len(companies), _MAX_WORKERS)
        with FutureManager(name="ValidatePortfolio", max_workers=worker_count) as manager:
            for index, company in enumerate(companies):
                prompt = template.format(
                    company_name=company.get("name", "unknown"),
                    company_url=company.get("url", ""),
                    firm_url=firm_url,
                )
                manager.submit_task(
                    self._validate_one,
                    prompt,
                    schema,
                    system_prompt,
                    f"validate_{index}",
                )
            results = manager.wait_for_all_and_collect_results()

        validated: list[dict[str, Any]] = []
        for label, data, _elapsed in results:
            index = int(label.split("_")[1])
            is_portfolio = data.get("is_portfolio_company", True)
            if is_portfolio:
                validated.append(companies[index])
            else:
                company = companies[index]
                logger.info(
                    "[ValidatePortfolio] filtered out: %s (%s)",
                    company.get("name", "unknown"),
                    company.get("url", ""),
                )

        logger.info(
            "[ValidatePortfolio] result: %d/%d companies validated",
            len(validated),
            len(companies),
        )

        self.request_executor.add_details(
            {
                "portfolio_companies": validated,
                "portfolio_count": len(validated),
                "portfolio_validated_from": len(companies),
            }
        )
        self.request_executor.mark_question_complete("validate_portfolio")

    def _validate_one(
        self,
        prompt: str,
        schema: dict[str, Any],
        system_prompt: str,
        label: str,
    ) -> tuple[str, dict[str, Any], float]:
        """Run a single validation AI call, returning fail-open default on error."""
        try:
            return run_structured_ai_call(
                ai_client_factory=self._ai_client_factory,
                user_prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                label=label,
                step_name="ValidatePortfolio",
            )
        except Exception:
            logger.exception("[ValidatePortfolio:%s] AI call failed — keeping company", label)
            return label, {"is_portfolio_company": True}, 0.0
