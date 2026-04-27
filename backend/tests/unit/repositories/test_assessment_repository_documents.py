"""Tests for document persistence on DynamoDBAssessmentRepository."""

from moto import mock_aws

from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository


class TestDocumentOperations:
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
