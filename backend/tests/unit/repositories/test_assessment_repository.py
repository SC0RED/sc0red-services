"""Tests for DynamoDBAssessmentRepository."""

import json

from moto import mock_aws

from src.repositories.dynamodb._tombstones import (
    DELETED_AT_FIELD,
    TTL_FIELD,
)
from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository


class TestAssessmentRepository:
    @mock_aws
    def test_save_and_get(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)

        assessment_id = repo.save(
            {
                "id": "assess-1",
                "company_id": "comp-1",
                "overall_score": 7.0,
                "tier": "high",
            }
        )

        assert assessment_id == "assess-1"

        result = repo.get_by_id("assess-1")
        assert result is not None
        assert result["tier"] == "high"

    @mock_aws
    def test_save_risk_score_and_get(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-2", "company_id": "comp-1"})

        repo.save_risk_score(
            "assess-2",
            "competitive_displacement",
            {
                "score": 8,
                "rationale": "High competition with competitor growth",
            },
        )
        repo.save_risk_score(
            "assess-2",
            "technology_obsolescence",
            {
                "score": 4,
                "rationale": "Moderate tech risk",
            },
        )

        scores = repo.get_risk_scores("assess-2")
        assert len(scores) == 2

    @mock_aws
    def test_save_opportunity_and_get(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-3", "company_id": "comp-1"})

        repo.save_opportunity(
            "assess-3",
            0,
            {
                "title": "Deploy AI Chatbot",
                "impact_rating": "High",
            },
        )
        repo.save_opportunity(
            "assess-3",
            1,
            {
                "title": "Automate QA",
                "impact_rating": "Medium",
            },
        )

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

    @mock_aws
    def test_save_with_top_risks_list(self, dynamodb_table):
        """top_risks list is JSON-serialized on save."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        risks = [{"category": "market", "score": 8}, {"category": "tech", "score": 5}]
        assessment_id = repo.save(
            {
                "id": "assess-risks",
                "company_id": "comp-1",
                "top_risks": risks,
            }
        )

        # Read raw item to verify serialization
        raw = dynamodb_table.get_item(
            pk=f"ASSESSMENT#{assessment_id}",
            sk="ASSESSMENT#METADATA",
        )
        assert isinstance(raw["top_risks"], str)
        assert json.loads(raw["top_risks"]) == risks

    @mock_aws
    def test_save_without_company_id(self, dynamodb_table):
        """When company_id is absent, no GSI3 attributes are written."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        assessment_id = repo.save(
            {
                "id": "assess-no-company",
                "tier": "medium",
            }
        )

        raw = dynamodb_table.get_item(
            pk=f"ASSESSMENT#{assessment_id}",
            sk="ASSESSMENT#METADATA",
        )
        assert "GSI3PK" not in raw
        assert "GSI3SK" not in raw

    @mock_aws
    def test_save_with_explicit_id(self, dynamodb_table):
        """save() with an explicit id persists under that id."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "custom-id-123", "tier": "high", "company_id": "comp-5"})

        result = repo.get_by_id("custom-id-123")
        assert result is not None
        assert result["tier"] == "high"
        assert result["id"] == "custom-id-123"

    @mock_aws
    def test_save_and_get_ebitda_tree(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-ebitda", "company_id": "comp-1"})

        tree_data = [
            {
                "id": "revenue",
                "label": "Total Revenue",
                "type": "revenue",
                "description": "All revenue",
                "linked_opportunity_indices": [],
                "children": [],
            },
        ]
        repo.save_ebitda_tree(
            "assess-ebitda",
            {
                "tree_data": tree_data,
                "revenue_estimate": "$10M-$50M",
                "ebitda_estimate": "$2M-$8M",
                "business_model_summary": "SaaS model overview",
            },
        )

        result = repo.get_ebitda_tree("assess-ebitda")
        assert result is not None
        assert result["revenueEstimate"] == "$10M-$50M"
        assert result["ebitdaEstimate"] == "$2M-$8M"
        assert result["businessModelSummary"] == "SaaS model overview"
        assert len(result["treeData"]) == 1
        assert result["treeData"][0]["id"] == "revenue"

    @mock_aws
    def test_get_ebitda_tree_not_found(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        result = repo.get_ebitda_tree("nonexistent")
        assert result is None

    @mock_aws
    def test_delete_cascades_ebitda_tree(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-del-ebitda", "company_id": "comp-1"})
        repo.save_ebitda_tree(
            "assess-del-ebitda",
            {
                "tree_data": [],
                "revenue_estimate": "$1M",
                "ebitda_estimate": "$100K",
                "business_model_summary": "Test",
            },
        )

        repo.delete("assess-del-ebitda")
        assert repo.get_ebitda_tree("assess-del-ebitda") is None

    # ── Document operations ─────────────────────────────────────────

    @mock_aws
    def test_batch_save_risk_scores(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-batch-rs", "company_id": "comp-1"})

        scores = [
            {"category": "competitive_displacement", "score": 8, "rationale": "High"},
            {"category": "data_ip", "score": 3, "rationale": "Low"},
        ]
        repo.batch_save_risk_scores("assess-batch-rs", scores)

        result = repo.get_risk_scores("assess-batch-rs")
        assert len(result) == 2
        categories = {r["category"] for r in result}
        assert categories == {"competitive_displacement", "data_ip"}

    @mock_aws
    def test_batch_save_opportunities(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-batch-opp", "company_id": "comp-1"})

        opportunities = [
            {
                "title": "Deploy AI Chatbot",
                "impact_rating": "High",
                "implementation_steps": ["Step 1", "Step 2"],
                "value_lever": "Revenue Side",
            },
            {
                "title": "Automate QA",
                "impact_rating": "Medium",
                "implementation_steps": [],
                "value_lever": "Cost Side",
            },
        ]
        repo.batch_save_opportunities("assess-batch-opp", opportunities)

        result = repo.get_opportunities("assess-batch-opp")
        assert len(result) == 2
        titles = {r["title"] for r in result}
        assert titles == {"Deploy AI Chatbot", "Automate QA"}

    @mock_aws
    def test_get_opportunities_scrubs_legacy_related_services(self, dynamodb_table):
        """Historical rows may still carry a `related_services` attribute.

        The repository must scrub it so the removed field never leaks to the
        API response. See openspec/changes/opportunities-cta-sc0red Phase 2.
        """
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-legacy", "company_id": "comp-1"})
        # Simulate a historical row written before Phase 2 by writing the
        # attribute directly — bypassing save_opportunity, which no longer
        # writes the field.
        repo._table.put_item(
            {
                "pk": "ASSESSMENT#assess-legacy",
                "sk": "OPP#0000",
                "entity_type": "opportunity",
                "assessment_id": "assess-legacy",
                "sort_order": 0,
                "title": "Legacy opportunity",
                "implementation_steps": "[\"Step 1\"]",
                "related_services": "[\"Datadog - Observability\"]",
            }
        )

        result = repo.get_opportunities("assess-legacy")
        assert len(result) == 1
        assert "related_services" not in result[0]
        assert result[0]["implementation_steps"] == ["Step 1"]

    @mock_aws
    def test_delete_analysis_results_keeps_documents_and_metadata(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-partial", "company_id": "comp-1"})
        repo.save_risk_score("assess-partial", "data_ip", {"score": 5})
        repo.save_opportunity("assess-partial", 0, {"title": "Opp"})
        repo.save_ebitda_tree(
            "assess-partial",
            {
                "tree_data": [],
                "revenue_estimate": "$1M",
                "ebitda_estimate": "$100K",
                "business_model_summary": "Test",
            },
        )
        repo.save_document(
            "assess-partial",
            {
                "id": "doc-keep",
                "filename": "keep.txt",
                "file_type": "txt",
                "extracted_text": "keep this",
                "char_count": 9,
                "uploaded_at": "2026-03-13T00:00:00",
            },
        )

        repo.delete_analysis_results("assess-partial")

        # Results are deleted
        assert repo.get_risk_scores("assess-partial") == []
        assert repo.get_opportunities("assess-partial") == []
        assert repo.get_ebitda_tree("assess-partial") is None
        # Metadata and documents are preserved
        assert repo.get_by_id("assess-partial") is not None
        assert len(repo.get_documents("assess-partial")) == 1

    # ── Soft-delete (tombstone) tests ────────────────────────────────

    @mock_aws
    def test_tombstone_hides_from_get_by_id(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-tomb", "company_id": "comp-1"})
        assert repo.get_by_id("assess-tomb") is not None

        repo.tombstone("assess-tomb")
        assert repo.get_by_id("assess-tomb") is None

    @mock_aws
    def test_tombstone_hides_from_find_by_company(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "live", "company_id": "comp-X"})
        repo.save({"id": "doomed", "company_id": "comp-X"})
        repo.tombstone("doomed")

        results = repo.find_by_company("comp-X")
        ids = sorted(item["id"] for item in results)
        assert ids == ["live"]

        # Recovery-aware variant still surfaces both.
        all_results = repo.find_by_company_with_deleted("comp-X")
        all_ids = sorted(item["id"] for item in all_results)
        assert all_ids == ["doomed", "live"]

    @mock_aws
    def test_get_by_id_with_deleted_returns_tombstoned(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-rec", "company_id": "comp-1"})
        repo.tombstone("assess-rec")

        item = repo.get_by_id_with_deleted("assess-rec")
        assert item is not None
        assert item["id"] == "assess-rec"
        assert item.get(DELETED_AT_FIELD)

    @mock_aws
    def test_restore_clears_tombstone(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-restore", "company_id": "comp-1"})
        repo.tombstone("assess-restore")
        assert repo.get_by_id("assess-restore") is None

        repo.restore("assess-restore")
        item = repo.get_by_id("assess-restore")
        assert item is not None
        assert DELETED_AT_FIELD not in item
        assert TTL_FIELD not in item

    @mock_aws
    def test_tombstone_does_not_touch_child_items(self, dynamodb_table):
        """Tombstoning the metadata leaves risk/opp/etc. children intact.

        Once metadata is tombstoned the assessment is invisible to live
        reads, so callers never reach the children. We rely on TTL +
        the cleanup script to drain children after the metadata evicts.
        """
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-c", "company_id": "comp-1"})
        repo.save_risk_score("assess-c", "data_ip", {"score": 5})
        repo.save_opportunity("assess-c", 0, {"title": "Opp"})

        repo.tombstone("assess-c")

        # Children are still in the table — only the metadata is hidden.
        assert repo.get_risk_scores("assess-c") != []
        assert repo.get_opportunities("assess-c") != []

        # And the parent metadata is hidden from live reads but not
        # actually removed.
        assert repo.get_by_id("assess-c") is None
        assert repo.get_by_id_with_deleted("assess-c") is not None
