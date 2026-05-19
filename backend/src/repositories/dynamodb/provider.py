"""StorageProvider factory for DynamoDB repositories."""

from __future__ import annotations

from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository
from src.repositories.dynamodb.client import DynamoDBTable
from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository
from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository
from src.repositories.dynamodb.user_repository import (
    DynamoDBInvitationRepository,
    DynamoDBOrganizationRepository,
    DynamoDBUserRepository,
)


class DynamoDBStorageProvider:
    """Bundles all DynamoDB repository factories for sc0red Services."""

    def __init__(self, table: DynamoDBTable | None = None) -> None:
        self._table = table or DynamoDBTable()

    @property
    def table(self) -> DynamoDBTable:
        """Return the underlying DynamoDB table wrapper."""
        return self._table

    def create_company_repository(self) -> DynamoDBCompanyRepository:
        """Return a new DynamoDBCompanyRepository backed by the shared table."""
        return DynamoDBCompanyRepository(self._table)

    def create_assessment_repository(self) -> DynamoDBAssessmentRepository:
        """Return a new DynamoDBAssessmentRepository backed by the shared table."""
        return DynamoDBAssessmentRepository(self._table)

    def create_scan_repository(self) -> DynamoDBScanRepository:
        """Return a new DynamoDBScanRepository backed by the shared table."""
        return DynamoDBScanRepository(self._table)

    def create_user_repository(self) -> DynamoDBUserRepository:
        """Return a new DynamoDBUserRepository backed by the shared table."""
        return DynamoDBUserRepository(self._table)

    def create_invitation_repository(self) -> DynamoDBInvitationRepository:
        """Return a new DynamoDBInvitationRepository backed by the shared table."""
        return DynamoDBInvitationRepository(self._table)

    def create_organization_repository(self) -> DynamoDBOrganizationRepository:
        """Return a new DynamoDBOrganizationRepository backed by the shared table."""
        return DynamoDBOrganizationRepository(self._table)
