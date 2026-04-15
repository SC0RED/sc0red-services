"""Portfolio scan pipeline factory.

Two-step pipeline: discover portfolio companies, then validate each one
with an AI call to filter false positives (nav links, firm pages, etc.).
Individual company analyses are dispatched separately (via SQS in production).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from signalfield_core.pipeline.factory import PipelineFactory

from src.pipeline.pipeline_steps.discover_portfolio import DiscoverPortfolio
from src.pipeline.pipeline_steps.validate_portfolio import ValidatePortfolioCompanies
from src.pipeline.request_executor import JanusRequestExecutor

if TYPE_CHECKING:
    from signalfield_core.pipeline.step import RequestStep
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor


class PortfolioScanFactory(PipelineFactory):
    """Builds and executes the portfolio discovery pipeline."""

    def __init__(
        self,
        entity_accessor: CompanyAccessor,
        ai_client_factory: AIClientFactory | None = None,
        tenant_id: str | None = None,
        request_id: str = "",
        scan_id: str = "",
    ) -> None:
        self._entity_accessor = entity_accessor
        self._ai_client_factory = ai_client_factory
        self._tenant_id = tenant_id
        self._request_id = request_id
        self._scan_id = scan_id

    def get_pipeline(self) -> list[RequestStep]:
        """Return the ordered list of pipeline steps for portfolio scanning."""
        return [
            DiscoverPortfolio(ai_client_factory=self._ai_client_factory),
            ValidatePortfolioCompanies(ai_client_factory=self._ai_client_factory),
        ]

    def build_executor(self) -> JanusRequestExecutor:
        """Build and wire a JanusRequestExecutor with the portfolio scan pipeline."""
        pipeline = self.get_pipeline()
        executor = JanusRequestExecutor(
            tenant_id=self._tenant_id,
            request_id=self._request_id,
            pipeline=pipeline,
            scan_id=self._scan_id,
        )
        for step in pipeline:
            step.request_executor = executor
            step.entity_accessor = self._entity_accessor
        return executor

    def execute_pipeline(self) -> JanusRequestExecutor:
        """Build executor, run pipeline, return executor with results."""
        executor = self.build_executor()
        executor.execute_all()
        return executor
