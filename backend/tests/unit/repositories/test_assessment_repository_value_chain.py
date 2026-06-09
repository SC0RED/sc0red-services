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
                "grounded": True,
                "insufficient_data_reason": None,
                "provenance_basis": "Operating model derived from a saas template.",
            },
        )

        result = repo.get_value_chain("assess-vc")
        assert result is not None
        assert result["summary"] == "Two-step value chain"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["name"] == "Sourcing"
        assert result["grounded"] is True
        assert result["insufficientDataReason"] is None
        assert result["provenanceBasis"] == "Operating model derived from a saas template."

    @mock_aws
    def test_save_and_get_ungrounded_value_chain(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-vc-ungrounded", "company_id": "comp-1"})
        repo.save_value_chain(
            "assess-vc-ungrounded",
            {
                "steps": [],
                "summary": "",
                "grounded": False,
                "insufficient_data_reason": "Could not determine how this business operates.",
                "provenance_basis": None,
            },
        )
        result = repo.get_value_chain("assess-vc-ungrounded")
        assert result is not None
        assert result["grounded"] is False
        assert result["insufficientDataReason"] == "Could not determine how this business operates."
        assert result["steps"] == []

    @mock_aws
    def test_get_value_chain_legacy_record_defaults_to_grounded(self, dynamodb_table):
        """A record stored before the grounding fields existed reads as grounded."""
        import json

        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-vc-legacy", "company_id": "comp-1"})
        dynamodb_table.put_item(
            {
                "pk": "ASSESSMENT#assess-vc-legacy",
                "sk": "VALUE_CHAIN",
                "entity_type": "value_chain",
                "assessment_id": "assess-vc-legacy",
                "steps": json.dumps([{"name": "Sourcing", "description": "Buy inputs"}]),
                "summary": "Legacy chain",
            }
        )
        result = repo.get_value_chain("assess-vc-legacy")
        assert result is not None
        assert result["grounded"] is True
        assert result["insufficientDataReason"] is None
        assert result["provenanceBasis"] is None

    @mock_aws
    def test_get_value_chain_returns_none_when_missing(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-vc-missing", "company_id": "comp-1"})
        assert repo.get_value_chain("assess-vc-missing") is None
