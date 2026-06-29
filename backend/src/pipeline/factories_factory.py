"""Central DI wiring — routes events to the correct pipeline factory.

Inspired by engine's PartsFactoriesFactory but simplified for sc0red Services.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from signalfield_core.models.enums import AIProviderType
from signalfield_core.services.ai_client_factory import AIClientFactory
from signalfield_core.services.resources.anthropic_resource import AnthropicResource
from signalfield_core.services.resources.openai_resource import OpenAIResource
from signalfield_core.services.service_ops import CompositeServiceOps

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import Company
from src.pipeline.pipeline_factories.company_analysis_factory import CompanyAnalysisFactory
from src.pipeline.pipeline_factories.portfolio_deepen_factory import PortfolioDeepenFactory
from src.pipeline.pipeline_factories.portfolio_scan_factory import PortfolioScanFactory
from src.pipeline.pipeline_factories.portfolio_source_url_factory import PortfolioSourceUrlFactory

if TYPE_CHECKING:
    from src.models.model_event import Sc0redServicesEvent
    from src.pipeline.request_executor import Sc0redServicesRequestExecutor
    from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository
    from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository
    from src.repositories.dynamodb.discovery_cache_repository import DiscoveryCacheRepository


def _initialize_ai_client_factory() -> AIClientFactory:
    """Initialize the AI provider resource and return a shared AIClientFactory."""
    ai_provider = os.environ.get("AI_PROVIDER", AIProviderType.ANTHROPIC.value)

    if ai_provider == AIProviderType.OPENAI.value:
        openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        if not openai_api_key:
            raise RuntimeError("OPENAI_API_KEY must be set when AI_PROVIDER=openai")
        if not OpenAIResource.is_initialized():
            OpenAIResource.initialize({"openai_api_key": openai_api_key})
    else:
        anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY must be set when AI_PROVIDER=anthropic")
        if not AnthropicResource.is_initialized():
            AnthropicResource.initialize({"anthropic_api_key": anthropic_api_key})

    composite_service_ops = CompositeServiceOps()
    return AIClientFactory(composite_service_ops, provider_type=ai_provider)


class Sc0redServicesFactoriesFactory:
    """Creates the correct pipeline factory for a given event."""

    def __init__(
        self,
        company_repo: DynamoDBCompanyRepository | None = None,
        assessment_repo: DynamoDBAssessmentRepository | None = None,
        discovery_cache_repo: DiscoveryCacheRepository | None = None,
    ) -> None:
        self._company_repo = company_repo
        self._assessment_repo = assessment_repo
        self._discovery_cache_repo = discovery_cache_repo
        self._ai_client_factory = _initialize_ai_client_factory()

    def create_and_execute(
        self,
        event: Sc0redServicesEvent,
        document_text: str | None = None,
    ) -> Sc0redServicesRequestExecutor:
        """Create the appropriate pipeline, execute it, and return the executor."""
        company = Company(
            id=event.request_id,
            url=event.url,
            scan_id=event.scan_id,
            org_id=event.org_id,
            user_id=event.user_id,
            company_name=event.company_name,
            document_text=document_text,
        )
        accessor = CompanyAccessor(company)

        if event.request_type == "portfolio_scan":
            factory = PortfolioScanFactory(
                entity_accessor=accessor,
                ai_client_factory=self._ai_client_factory,
                tenant_id=event.tenant_id,
                request_id=event.request_id,
                scan_id=event.scan_id,
                discovery_cache_repo=self._discovery_cache_repo,
            )
        elif event.request_type == "portfolio_deepen":
            factory = PortfolioDeepenFactory(
                entity_accessor=accessor,
                ai_client_factory=self._ai_client_factory,
                tenant_id=event.tenant_id,
                request_id=event.request_id,
                scan_id=event.scan_id,
                # Schema-required for a deepen event — direct access so a missing
                # key fails loudly rather than silently running an unseeded search.
                seed_companies=event.extra["seed_companies"],
            )
        elif event.request_type == "portfolio_source_url":
            factory = PortfolioSourceUrlFactory(
                entity_accessor=accessor,
                ai_client_factory=self._ai_client_factory,
                tenant_id=event.tenant_id,
                request_id=event.request_id,
                scan_id=event.scan_id,
                seed_companies=event.extra["seed_companies"],
            )
        else:
            factory = CompanyAnalysisFactory(
                entity_accessor=accessor,
                ai_client_factory=self._ai_client_factory,
                tenant_id=event.tenant_id,
                request_id=event.request_id,
                company_repo=self._company_repo,
                assessment_repo=self._assessment_repo,
                scan_id=event.scan_id,
            )

        return factory.execute_pipeline()
