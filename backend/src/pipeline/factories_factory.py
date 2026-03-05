"""Central DI wiring — routes events to the correct pipeline factory.

Inspired by engine's PartsFactoriesFactory but simplified for Janus.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_factories.company_analysis_factory import CompanyAnalysisFactory
from src.pipeline.pipeline_factories.portfolio_scan_factory import PortfolioScanFactory

if TYPE_CHECKING:
    from src.models.model_event import JanusEvent
    from src.pipeline.request_executor import JanusRequestExecutor
    from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository
    from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository


class JanusFactoriesFactory:
    """Creates the correct pipeline factory for a given event."""

    def __init__(
        self,
        company_repo: DynamoDBCompanyRepository | None = None,
        assessment_repo: DynamoDBAssessmentRepository | None = None,
    ) -> None:
        self._company_repo = company_repo
        self._assessment_repo = assessment_repo
        self._openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        self._model = os.environ.get("AI_MODEL", "gpt-4o")

    def create_and_execute(self, event: JanusEvent) -> JanusRequestExecutor:
        """Create the appropriate pipeline, execute it, and return the executor."""
        company = Company(
            id=event.request_id,
            url=event.url,
            scan_id=event.scan_id,
            org_id=event.org_id,
            company_name=event.company_name,
        )
        accessor = CompanyAccessor(company)

        if event.request_type == "portfolio_scan":
            factory = PortfolioScanFactory(
                entity_accessor=accessor,
                tenant_id=event.tenant_id,
                request_id=event.request_id,
            )
        else:
            factory = CompanyAnalysisFactory(
                entity_accessor=accessor,
                openai_api_key=self._openai_api_key,
                model=self._model,
                tenant_id=event.tenant_id,
                request_id=event.request_id,
                company_repo=self._company_repo,
                assessment_repo=self._assessment_repo,
            )

        return factory.execute_pipeline()
