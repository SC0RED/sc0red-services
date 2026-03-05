"""Tests for DynamoDBAssessmentRepository."""

from moto import mock_aws

from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository


class TestAssessmentRepository:
    @mock_aws
    def test_save_and_get(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)

        assessment_id = repo.save({
            "id": "assess-1",
            "company_id": "comp-1",
            "overall_score": 7.0,
            "tier": "high",
        })

        assert assessment_id == "assess-1"

        result = repo.get_by_id("assess-1")
        assert result is not None
        assert result["tier"] == "high"

    @mock_aws
    def test_save_risk_score_and_get(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-2", "company_id": "comp-1"})

        repo.save_risk_score("assess-2", "competitive_displacement", {
            "score": 8,
            "explanation": "High competition",
            "evidence": ["competitor growth"],
        })
        repo.save_risk_score("assess-2", "technology_obsolescence", {
            "score": 4,
            "explanation": "Moderate tech risk",
        })

        scores = repo.get_risk_scores("assess-2")
        assert len(scores) == 2

    @mock_aws
    def test_save_opportunity_and_get(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-3", "company_id": "comp-1"})

        repo.save_opportunity("assess-3", 0, {
            "title": "Deploy AI Chatbot",
            "impact_rating": "High",
            "related_services": [{"service_type": "AI Consulting"}],
        })
        repo.save_opportunity("assess-3", 1, {
            "title": "Automate QA",
            "impact_rating": "Medium",
        })

        opps = repo.get_opportunities("assess-3")
        assert len(opps) == 2

    @mock_aws
    def test_find_by_company(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "a1", "company_id": "comp-X"})
        repo.save({"id": "a2", "company_id": "comp-X"})
        repo.save({"id": "a3", "company_id": "comp-Y"})

        results = repo.find_by_company("comp-X")
        assert len(results) == 2

    @mock_aws
    def test_delete_cascades(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-del", "company_id": "comp-1"})
        repo.save_risk_score("assess-del", "data_ip", {"score": 5})
        repo.save_opportunity("assess-del", 0, {"title": "Opp"})

        repo.delete("assess-del")

        assert repo.get_by_id("assess-del") is None
        assert repo.get_risk_scores("assess-del") == []
        assert repo.get_opportunities("assess-del") == []
