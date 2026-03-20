"""Company analysis pipeline factory.

Wires the 4-step single company analysis pipeline:
ScrapeAndResolve → ParallelProfileRiskAndIdeation →
ParallelOpportunityDetailsAndEbitda → PersistResults
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from signalfield_core.pipeline.factory import PipelineFactory

from src.pipeline.pipeline_steps.parallel_opportunities_ebitda import (
    ParallelOpportunityDetailsAndEbitda,
)
from src.pipeline.pipeline_steps.parallel_profile_risk import ParallelProfileRiskAndIdeation
from src.pipeline.pipeline_steps.persist_results import PersistResults
from src.pipeline.pipeline_steps.scrape_and_resolve import ScrapeAndResolveURL
from src.pipeline.request_executor import JanusRequestExecutor

if TYPE_CHECKING:
    from signalfield_core.pipeline.step import RequestStep
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor
    from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository
    from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository


class CompanyAnalysisFactory(PipelineFactory):
    """Builds and executes the single company analysis pipeline."""

    def __init__(
        self,
        entity_accessor: CompanyAccessor,
        ai_client_factory: AIClientFactory,
        tenant_id: str | None = None,
        request_id: str = "",
        company_repo: DynamoDBCompanyRepository | None = None,
        assessment_repo: DynamoDBAssessmentRepository | None = None,
    ) -> None:
        self._entity_accessor = entity_accessor
        self._ai_client_factory = ai_client_factory
        self._tenant_id = tenant_id
        self._request_id = request_id
        self._company_repo = company_repo
        self._assessment_repo = assessment_repo

    def get_pipeline(self) -> list[RequestStep]:
        """Return the ordered list of pipeline steps for company analysis."""
        return [
            ScrapeAndResolveURL(
                ai_client_factory=self._ai_client_factory,
            ),
            ParallelProfileRiskAndIdeation(
                ai_client_factory=self._ai_client_factory,
            ),
            ParallelOpportunityDetailsAndEbitda(
                ai_client_factory=self._ai_client_factory,
            ),
            PersistResults(
                company_repo=self._company_repo,
                assessment_repo=self._assessment_repo,
            ),
        ]

    def build_executor(self) -> JanusRequestExecutor:
        """Build and wire a JanusRequestExecutor with the company analysis pipeline."""
        pipeline = self.get_pipeline()
        executor = JanusRequestExecutor(
            tenant_id=self._tenant_id,
            request_id=self._request_id,
            pipeline=pipeline,
            company_repo=self._company_repo,
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
