"""Portfolio scan pipeline factory.

Single-step pipeline that discovers portfolio companies.
Individual company analyses are dispatched separately (via SQS in production).
"""

from __future__ import annotations

from signalfield_core.pipeline.factory import PipelineFactory
from signalfield_core.pipeline.step import RequestStep

from src.facades.company_accessor import CompanyAccessor
from src.pipeline.pipeline_steps.discover_portfolio import DiscoverPortfolio
from src.pipeline.request_executor import JanusRequestExecutor


class PortfolioScanFactory(PipelineFactory):
    """Builds and executes the portfolio discovery pipeline."""

    def __init__(
        self,
        entity_accessor: CompanyAccessor,
        tenant_id: str | None = None,
        request_id: str = "",
    ) -> None:
        self._entity_accessor = entity_accessor
        self._tenant_id = tenant_id
        self._request_id = request_id

    def get_pipeline(self) -> list[RequestStep]:
        return [DiscoverPortfolio()]

    def build_executor(self) -> JanusRequestExecutor:
        pipeline = self.get_pipeline()
        executor = JanusRequestExecutor(
            tenant_id=self._tenant_id,
            request_id=self._request_id,
            pipeline=pipeline,
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
