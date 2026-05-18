"""Tests for PDF-export persistence on DynamoDBAssessmentRepository.

Covers the PDF export sub-record lifecycle: save, get, and clear.
Mirrors the strategy-map tests' shape — same single-table key
(``sk = PDF_EXPORT``), same idempotent clear semantics.
"""

from moto import mock_aws

from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository


class TestPdfExportOperations:
    @mock_aws
    def test_save_and_get_pdf_export_rendering(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-pdf-1", "company_id": "comp-1"})

        repo.save_pdf_export(
            "assess-pdf-1",
            {
                "status": "rendering",
                "s3_key": "pdf-exports/assess-pdf-1.pdf",
                "started_at": "2026-05-18T10:00:00+00:00",
            },
        )

        result = repo.get_pdf_export("assess-pdf-1")
        assert result is not None
        assert result["status"] == "rendering"
        assert result["s3_key"] == "pdf-exports/assess-pdf-1.pdf"
        assert result["started_at"] == "2026-05-18T10:00:00+00:00"
        # Optional fields absent in rendering state.
        assert "generated_at" not in result
        assert "error" not in result

    @mock_aws
    def test_save_pdf_export_ready_includes_generated_at(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-pdf-2", "company_id": "comp-1"})

        repo.save_pdf_export(
            "assess-pdf-2",
            {
                "status": "ready",
                "s3_key": "pdf-exports/assess-pdf-2.pdf",
                "started_at": "2026-05-18T10:00:00+00:00",
                "generated_at": "2026-05-18T10:00:13+00:00",
            },
        )

        result = repo.get_pdf_export("assess-pdf-2")
        assert result is not None
        assert result["status"] == "ready"
        assert result["generated_at"] == "2026-05-18T10:00:13+00:00"

    @mock_aws
    def test_save_pdf_export_failed_includes_error(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-pdf-3", "company_id": "comp-1"})

        repo.save_pdf_export(
            "assess-pdf-3",
            {
                "status": "failed",
                "s3_key": "pdf-exports/assess-pdf-3.pdf",
                "started_at": "2026-05-18T10:00:00+00:00",
                "error": "Puppeteer crashed mid-render",
            },
        )

        result = repo.get_pdf_export("assess-pdf-3")
        assert result is not None
        assert result["status"] == "failed"
        assert result["error"] == "Puppeteer crashed mid-render"

    @mock_aws
    def test_save_pdf_export_overwrites_previous(self, dynamodb_table):
        """Second save replaces the first — one PDF_EXPORT row per analysis."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-pdf-4", "company_id": "comp-1"})

        repo.save_pdf_export(
            "assess-pdf-4",
            {
                "status": "rendering",
                "s3_key": "pdf-exports/assess-pdf-4.pdf",
                "started_at": "2026-05-18T10:00:00+00:00",
            },
        )
        repo.save_pdf_export(
            "assess-pdf-4",
            {
                "status": "ready",
                "s3_key": "pdf-exports/assess-pdf-4.pdf",
                "started_at": "2026-05-18T10:00:00+00:00",
                "generated_at": "2026-05-18T10:00:13+00:00",
            },
        )

        result = repo.get_pdf_export("assess-pdf-4")
        assert result is not None
        assert result["status"] == "ready"
        assert result["generated_at"] == "2026-05-18T10:00:13+00:00"

    @mock_aws
    def test_get_pdf_export_returns_none_when_absent(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-pdf-5", "company_id": "comp-1"})
        assert repo.get_pdf_export("assess-pdf-5") is None

    @mock_aws
    def test_clear_pdf_export_removes_persisted_record(self, dynamodb_table):
        """Re-analyse path: clear_pdf_export removes the persisted record."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-pdf-6", "company_id": "comp-1"})
        repo.save_pdf_export(
            "assess-pdf-6",
            {
                "status": "ready",
                "s3_key": "pdf-exports/assess-pdf-6.pdf",
                "started_at": "2026-05-18T10:00:00+00:00",
                "generated_at": "2026-05-18T10:00:13+00:00",
            },
        )
        assert repo.get_pdf_export("assess-pdf-6") is not None

        repo.clear_pdf_export("assess-pdf-6")
        assert repo.get_pdf_export("assess-pdf-6") is None

    @mock_aws
    def test_clear_pdf_export_is_idempotent(self, dynamodb_table):
        """Clearing when no record exists must not raise (idempotent semantics)."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-pdf-7", "company_id": "comp-1"})

        repo.clear_pdf_export("assess-pdf-7")
        repo.clear_pdf_export("assess-pdf-7")  # twice
        assert repo.get_pdf_export("assess-pdf-7") is None
