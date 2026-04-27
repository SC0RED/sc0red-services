"""Tests for value chain persistence on DynamoDBAssessmentRepository."""

from moto import mock_aws

from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository


class TestValueChainOperations:
    @mock_aws
    def test_save_and_get_value_chain(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-vc", "company_id": "comp-1"})

        repo.save_value_chain(
            "assess-vc",
            {
                "steps": [
                    {"name": "Sourcing", "description": "Buy inputs"},
                    {"name": "Delivery", "description": "Ship to customer"},
                ],
                "summary": "Two-step value chain",
            },
        )

        result = repo.get_value_chain("assess-vc")
        assert result is not None
        assert result["summary"] == "Two-step value chain"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["name"] == "Sourcing"

    @mock_aws
    def test_get_value_chain_returns_none_when_missing(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-vc-missing", "company_id": "comp-1"})
        assert repo.get_value_chain("assess-vc-missing") is None
