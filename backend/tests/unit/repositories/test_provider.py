"""Tests for DynamoDBStorageProvider."""

from unittest.mock import MagicMock

from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository
from src.repositories.dynamodb.company_repository import DynamoDBCompanyRepository
from src.repositories.dynamodb.provider import DynamoDBStorageProvider
from src.repositories.dynamodb.scan_repository import DynamoDBScanRepository
from src.repositories.dynamodb.user_repository import (
    DynamoDBOrganizationRepository,
    DynamoDBUserRepository,
)


class TestDynamoDBStorageProvider:
    def test_table_property(self):
        mock_table = MagicMock()
        provider = DynamoDBStorageProvider(table=mock_table)
        assert provider.table is mock_table

    def test_create_company_repository(self):
        mock_table = MagicMock()
        provider = DynamoDBStorageProvider(table=mock_table)
        repo = provider.create_company_repository()
        assert isinstance(repo, DynamoDBCompanyRepository)

    def test_create_assessment_repository(self):
        mock_table = MagicMock()
        provider = DynamoDBStorageProvider(table=mock_table)
        repo = provider.create_assessment_repository()
        assert isinstance(repo, DynamoDBAssessmentRepository)

    def test_create_scan_repository(self):
        mock_table = MagicMock()
        provider = DynamoDBStorageProvider(table=mock_table)
        repo = provider.create_scan_repository()
        assert isinstance(repo, DynamoDBScanRepository)

    def test_create_user_repository(self):
        mock_table = MagicMock()
        provider = DynamoDBStorageProvider(table=mock_table)
        repo = provider.create_user_repository()
        assert isinstance(repo, DynamoDBUserRepository)

    def test_create_organization_repository(self):
        mock_table = MagicMock()
        provider = DynamoDBStorageProvider(table=mock_table)
        repo = provider.create_organization_repository()
        assert isinstance(repo, DynamoDBOrganizationRepository)
