"""Tests for DynamoDBRequestRepository."""

from moto import mock_aws

from src.repositories.dynamodb.request_repository import DynamoDBRequestRepository


class TestRequestRepository:
    @mock_aws
    def test_create_and_find(self, dynamodb_table):
        repo = DynamoDBRequestRepository(dynamodb_table)
        request_id = repo.create(
            {
                "request_type": "company_analysis",
                "url": "https://example.com",
                "status": "pending",
            }
        )

        assert request_id is not None

        result = repo.find_by_request_id(request_id)
        assert result is not None
        assert result["status"] == "pending"
        assert result["url"] == "https://example.com"
        assert "created_at" in result

    @mock_aws
    def test_update_status(self, dynamodb_table):
        repo = DynamoDBRequestRepository(dynamodb_table)
        request_id = repo.create({"status": "pending"})

        repo.update_status(request_id, {"status": "complete", "progress": 100})

        result = repo.find_by_request_id(request_id)
        assert result["status"] == "complete"
        assert result["progress"] == 100

    @mock_aws
    def test_add_details(self, dynamodb_table):
        repo = DynamoDBRequestRepository(dynamodb_table)
        request_id = repo.create({"status": "running"})

        repo.add_details(request_id, {"step_1": "done", "step_2": "done"})

        result = repo.find_by_request_id(request_id)
        assert result["detail_step_1"] == "done"
        assert result["detail_step_2"] == "done"

    @mock_aws
    def test_delete(self, dynamodb_table):
        repo = DynamoDBRequestRepository(dynamodb_table)
        request_id = repo.create({"status": "pending"})

        repo.delete(request_id)
        assert repo.find_by_request_id(request_id) is None
