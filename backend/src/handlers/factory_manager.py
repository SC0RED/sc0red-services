"""Request lifecycle manager — creates factories and manages request state."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from src.models.model_event import JanusEvent
from src.pipeline.factories_factory import JanusFactoriesFactory
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory


class FactoryManager:
    """Manages the lifecycle of a pipeline request."""

    def __init__(self, storage: DynamoDBStorageProvider | None = None) -> None:
        self._storage = storage or DynamoDBStorageProvider()
        self._factories_factory = JanusFactoriesFactory(
            company_repo=self._storage.create_company_repository(),
            assessment_repo=self._storage.create_assessment_repository(),
        )

    @property
    def storage(self) -> DynamoDBStorageProvider:
        """Return the storage provider."""
        return self._storage

    def get_ai_client_factory(self) -> AIClientFactory:
        """Return the shared AI client factory for ad-hoc AI calls."""
        return self._factories_factory._ai_client_factory

    def run_company_analysis(
        self,
        url: str,
        org_id: str,
        user_id: str,
        scan_id: str,
        company_name: str = "",
        request_id: str | None = None,
        document_text: str | None = None,
    ) -> dict[str, Any]:
        """Run a single company analysis pipeline."""
        if request_id is None:
            raise ValueError("request_id is required — callers must pre-generate a UUID")

        event = JanusEvent(
            request_id=request_id,
            request_type="company_analysis",
            url=url,
            org_id=org_id,
            user_id=user_id,
            scan_id=scan_id,
            company_name=company_name,
            tenant_id=org_id,
        )

        executor = self._factories_factory.create_and_execute(event, document_text=document_text)

        return {
            "request_id": request_id,
            "details": executor.details,
            "step_timings": executor.step_timings,
            "exceptions": [str(e) for e in executor.exceptions],
        }

    def run_portfolio_discovery(
        self,
        url: str,
        org_id: str,
        user_id: str,
        scan_id: str,
    ) -> dict[str, Any]:
        """Run portfolio discovery pipeline."""
        request_id = str(uuid.uuid4())
        event = JanusEvent(
            request_id=request_id,
            request_type="portfolio_scan",
            url=url,
            org_id=org_id,
            user_id=user_id,
            scan_id=scan_id,
            tenant_id=org_id,
        )

        executor = self._factories_factory.create_and_execute(event)

        return {
            "request_id": request_id,
            "details": executor.details,
            "step_timings": executor.step_timings,
            "exceptions": [str(e) for e in executor.exceptions],
        }
