"""Company analysis pipeline factory.

Wires the 5-step single company analysis pipeline:
ScrapeAndResolve → ExtractProfile → AssessRisk → GenerateOpportunities → PersistResults
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from signalfield_core.pipeline.factory import PipelineFactory
from signalfield_core.pipeline.step import RequestStep

from src.facades.company_accessor import CompanyAccessor
from src.pipeline.pipeline_steps.assess_risk import AssessRisk
from src.pipeline.pipeline_steps.extract_profile import ExtractProfile
from src.pipeline.pipeline_steps.generate_opportunities import GenerateOpportunities
from src.pipeline.pipeline_steps.persist_results import PersistResults
from src.pipeline.pipeline_steps.scrape_and_resolve import ScrapeAndResolveURL
from src.pipeline.request_executor import JanusRequestExecutor

if TYPE_CHECKING:
    from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository
    from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository


class CompanyAnalysisFactory(PipelineFactory):
    """Builds and executes the single company analysis pipeline."""

    def __init__(
        self,
        entity_accessor: CompanyAccessor,
        openai_api_key: str,
        model: str = "gpt-4o",
        tenant_id: str | None = None,
        request_id: str = "",
        company_repo: DynamoDBCompanyRepository | None = None,
        assessment_repo: DynamoDBAssessmentRepository | None = None,
    ) -> None:
        self._entity_accessor = entity_accessor
        self._openai_api_key = openai_api_key
        self._model = model
        self._tenant_id = tenant_id
        self._request_id = request_id
        self._company_repo = company_repo
        self._assessment_repo = assessment_repo

    def get_pipeline(self) -> list[RequestStep]:
        return [
            ScrapeAndResolveURL(
                openai_api_key=self._openai_api_key,
                model=self._model,
            ),
            ExtractProfile(
                openai_api_key=self._openai_api_key,
                model=self._model,
            ),
            AssessRisk(
                openai_api_key=self._openai_api_key,
                model=self._model,
            ),
            GenerateOpportunities(
                openai_api_key=self._openai_api_key,
                model=self._model,
            ),
            PersistResults(
                company_repo=self._company_repo,
                assessment_repo=self._assessment_repo,
            ),
        ]

    def build_executor(self) -> JanusRequestExecutor:
        pipeline = self.get_pipeline()
        executor = JanusRequestExecutor(
            tenant_id=self._tenant_id,
            request_id=self._request_id,
            pipeline=pipeline,
        )
        # Wire entity accessor and executor into all steps
        for step in pipeline:
            step.request_executor = executor
            step.entity_accessor = self._entity_accessor
        return executor

    def execute_pipeline(self) -> JanusRequestExecutor:
        """Build executor, run pipeline, return executor with results."""
        executor = self.build_executor()
        executor.execute_all()
        return executor
