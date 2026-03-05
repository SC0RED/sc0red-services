"""StorageProvider factory for DynamoDB repositories."""

from __future__ import annotations

from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository
from src.repositories.dynamodb.client import DynamoDBTable
from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository
from src.repositories.dynamodb.request_repository import DynamoDBRequestRepository
from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository
from src.repositories.dynamodb.user_repository import (
    DynamoDBOrganizationRepository,
    DynamoDBUserRepository,
)


class DynamoDBStorageProvider:
    """Bundles all DynamoDB repository factories for Janus."""

    def __init__(self, table: DynamoDBTable | None = None) -> None:
        self._table = table or DynamoDBTable()

    @property
    def table(self) -> DynamoDBTable:
        return self._table

    def create_company_repository(self) -> DynamoDBCompanyRepository:
        return DynamoDBCompanyRepository(self._table)

    def create_assessment_repository(self) -> DynamoDBAssessmentRepository:
        return DynamoDBAssessmentRepository(self._table)

    def create_request_repository(self) -> DynamoDBRequestRepository:
        return DynamoDBRequestRepository(self._table)

    def create_scan_repository(self) -> DynamoDBScanRepository:
        return DynamoDBScanRepository(self._table)

    def create_user_repository(self) -> DynamoDBUserRepository:
        return DynamoDBUserRepository(self._table)

    def create_organization_repository(self) -> DynamoDBOrganizationRepository:
        return DynamoDBOrganizationRepository(self._table)
