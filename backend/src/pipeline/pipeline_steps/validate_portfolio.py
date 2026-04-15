"""Pipeline step: validate discovered portfolio companies with AI.

Uses parallel AI calls via FutureManager to confirm each discovered URL
is genuinely a portfolio company (not a firm page, nav link, or tool).
Fail-open: companies whose validation call errors are kept.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.exceptions.base import EngineError
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
        """Validate remainder companies and merge with auto-included high-confidence ones.

        ``portfolio_companies`` from ``DiscoverPortfolio`` contains only the
        remainder (found by one discovery path). ``portfolio_auto_included``
        contains the intersection (found by both paths) — these skip AI
        validation to save time and cost.
        """
        details = self.request_executor.details
        candidates = cast("list[dict[str, Any]]", details.get("portfolio_companies", []))
        auto_included = cast(
            "list[dict[str, Any]]", details.get("portfolio_auto_included", [])
        )

        if not candidates:
            # Nothing to validate — final list is just the auto-included set.
            final = list(auto_included)
            self.request_executor.add_details(
                {
                    "portfolio_companies": final,
                    "portfolio_count": len(final),
                    "portfolio_validated_from": 0,
                }
            )
            self.request_executor.mark_question_complete("validate_portfolio")
            return

        if not self._ai_client_factory:
            # No AI — fail-open: keep all candidates alongside auto-included.
            final = auto_included + candidates
            self.request_executor.add_details(
                {
                    "portfolio_companies": final,
                    "portfolio_count": len(final),
                    "portfolio_validated_from": len(candidates),
                }
            )
            self.request_executor.mark_question_complete("validate_portfolio")
            return

        accessor = cast("CompanyAccessor", self.entity_accessor)
        firm_url = accessor.company.url

        system_prompt = load_system_prompt("portfolio_validation")
        template = load_template("portfolio_validation")
        schema = load_schema("portfolio_validation")

        worker_count = min(len(candidates), _MAX_WORKERS)
        results: list[tuple[str, dict[str, Any], float]] = []
        with FutureManager(name="ValidatePortfolio", max_workers=worker_count) as manager:
            for index, company in enumerate(candidates):
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
                validated.append(candidates[index])
            else:
                company = candidates[index]
                logger.info(
                    "[ValidatePortfolio] filtered out: %s (%s)",
                    company.get("name", "unknown"),
                    company.get("url", ""),
                )

        final = auto_included + validated
        logger.info(
            "[ValidatePortfolio] result: %d validated from %d candidates, "
            "+%d auto-included = %d total",
            len(validated),
            len(candidates),
            len(auto_included),
            len(final),
        )

        self.request_executor.add_details(
            {
                "portfolio_companies": final,
                "portfolio_count": len(final),
                "portfolio_validated_from": len(candidates),
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
        except (EngineError, ValueError, RuntimeError):
            logger.exception("[ValidatePortfolio:%s] AI call failed — keeping company", label)
            return label, {"is_portfolio_company": True}, 0.0
