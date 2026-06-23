"""Portfolio provided-source-URL pipeline factory.

Scrapes a customer-supplied reliable URL (``FetchProvidedSource``) and validates
the newly-found companies, merging them into the scan's existing list. Mirrors
the deepen factory but the first step reads a real page instead of web search.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from signalfield_core.pipeline.factory import PipelineFactory

from src.pipeline.pipeline_steps.fetch_provided_source import FetchProvidedSource
from src.pipeline.pipeline_steps.validate_portfolio import ValidatePortfolioCompanies
from src.pipeline.request_executor import Sc0redServicesRequestExecutor

if TYPE_CHECKING:
    from signalfield_core.pipeline.step import RequestStep
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor


class PortfolioSourceUrlFactory(PipelineFactory):
    """Builds and executes the provided-source-URL pipeline."""

    def __init__(
        self,
        entity_accessor: CompanyAccessor,
        ai_client_factory: AIClientFactory | None = None,
        tenant_id: str | None = None,
        request_id: str = "",
        scan_id: str = "",
        seed_companies: list[dict[str, str]] | None = None,
    ) -> None:
        self._entity_accessor = entity_accessor
        self._ai_client_factory = ai_client_factory
        self._tenant_id = tenant_id
        self._request_id = request_id
        self._scan_id = scan_id
        self._seed_companies = seed_companies or []

    def get_pipeline(self) -> list[RequestStep]:
        """Return the ordered list of pipeline steps for a provided source URL."""
        return [
            FetchProvidedSource(
                ai_client_factory=self._ai_client_factory,
                seed_companies=self._seed_companies,
            ),
            ValidatePortfolioCompanies(ai_client_factory=self._ai_client_factory),
        ]

    def build_executor(self) -> Sc0redServicesRequestExecutor:
        """Build and wire a Sc0redServicesRequestExecutor with the pipeline."""
        pipeline = self.get_pipeline()
        executor = Sc0redServicesRequestExecutor(
            tenant_id=self._tenant_id,
            request_id=self._request_id,
            pipeline=pipeline,
            scan_id=self._scan_id,
        )
        for step in pipeline:
            step.request_executor = executor
            step.entity_accessor = self._entity_accessor
        return executor

    def execute_pipeline(self) -> Sc0redServicesRequestExecutor:
        """Build executor, run pipeline, return executor with results."""
        executor = self.build_executor()
        executor.execute_all()
        return executor
