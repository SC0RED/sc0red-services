"""Tests for DynamoDBAssessmentRepository."""

import json

from moto import mock_aws

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
                "related_services": [{"service_type": "AI Consulting"}],
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
    def test_save_assessment_wrapper(self, dynamodb_table):
        """save_assessment() sets the id and delegates to save()."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save_assessment("custom-id-123", {"tier": "high", "company_id": "comp-5"})

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
    def test_save_and_get_documents(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-doc", "company_id": "comp-1"})

        repo.save_document(
            "assess-doc",
            {
                "id": "doc-1",
                "filename": "report.pdf",
                "file_type": "pdf",
                "extracted_text": "Revenue was $10M last year.",
                "char_count": 26,
                "uploaded_at": "2026-03-13T00:00:00",
            },
        )
        repo.save_document(
            "assess-doc",
            {
                "id": "doc-2",
                "filename": "memo.txt",
                "file_type": "txt",
                "extracted_text": "Investment memo content.",
                "char_count": 23,
                "uploaded_at": "2026-03-13T01:00:00",
            },
        )

        documents = repo.get_documents("assess-doc")
        assert len(documents) == 2
        filenames = {d["filename"] for d in documents}
        assert filenames == {"report.pdf", "memo.txt"}
        assert documents[0]["fileType"] in ("pdf", "txt")
        assert documents[0]["charCount"] > 0

    @mock_aws
    def test_delete_document(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-deldoc", "company_id": "comp-1"})
        repo.save_document(
            "assess-deldoc",
            {
                "id": "doc-del",
                "filename": "old.txt",
                "file_type": "txt",
                "extracted_text": "old content",
                "char_count": 11,
                "uploaded_at": "2026-03-13T00:00:00",
            },
        )

        repo.delete_document("assess-deldoc", "doc-del")
        documents = repo.get_documents("assess-deldoc")
        assert len(documents) == 0

    @mock_aws
    def test_get_combined_document_text(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-combined", "company_id": "comp-1"})
        repo.save_document(
            "assess-combined",
            {
                "id": "doc-a",
                "filename": "a.txt",
                "file_type": "txt",
                "extracted_text": "First document",
                "char_count": 14,
                "uploaded_at": "2026-03-13T00:00:00",
            },
        )
        repo.save_document(
            "assess-combined",
            {
                "id": "doc-b",
                "filename": "b.txt",
                "file_type": "txt",
                "extracted_text": "Second document",
                "char_count": 15,
                "uploaded_at": "2026-03-13T01:00:00",
            },
        )

        combined = repo.get_combined_document_text("assess-combined")
        assert "First document" in combined
        assert "Second document" in combined
        assert "---" in combined

    @mock_aws
    def test_get_combined_document_text_empty(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-empty-docs", "company_id": "comp-1"})
        combined = repo.get_combined_document_text("assess-empty-docs")
        assert combined == ""

    @mock_aws
    def test_delete_cascades_documents(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-cascade-doc", "company_id": "comp-1"})
        repo.save_document(
            "assess-cascade-doc",
            {
                "id": "doc-cascade",
                "filename": "test.txt",
                "file_type": "txt",
                "extracted_text": "content",
                "char_count": 7,
                "uploaded_at": "2026-03-13T00:00:00",
            },
        )

        repo.delete("assess-cascade-doc")
        assert repo.get_documents("assess-cascade-doc") == []

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
                "related_services": ["Accenture - AI strategy"],
                "implementation_steps": ["Step 1", "Step 2"],
                "value_lever": "Revenue Side",
            },
            {
                "title": "Automate QA",
                "impact_rating": "Medium",
                "related_services": [],
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
