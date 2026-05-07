"""Tests for strategy-map persistence on DynamoDBAssessmentRepository.

Covers the on-demand strategy-map lifecycle: save, get, and clear.
Per the strategy-map-on-demand spec, the repo provides ``clear_strategy_map``
so the re-analyse handler can invalidate a stale map before regenerating
the underlying diagnosis.
"""

from moto import mock_aws

from src.repositories.dynamodb.assessment_repository import DynamoDBAssessmentRepository


class TestStrategyMapOperations:
    @mock_aws
    def test_save_and_get_strategy_map(self, dynamodb_table):
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-sm", "company_id": "comp-1"})

        payload = {
            "vision": {"statement": "Be the best", "synthesised": False, "rationale": "..."},
            "mission": {"statement": "Serve customers", "synthesised": False, "rationale": "..."},
        }
        repo.save_strategy_map("assess-sm", payload)

        result = repo.get_strategy_map("assess-sm")
        assert result is not None
        assert result["vision"]["statement"] == "Be the best"

    @mock_aws
    def test_clear_strategy_map_removes_persisted_record(self, dynamodb_table):
        """Re-analyse path: clear_strategy_map removes the persisted record."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-clear", "company_id": "comp-1"})
        repo.save_strategy_map("assess-clear", {"vision": {"statement": "v"}})

        # Sanity: the map is there before clearing.
        assert repo.get_strategy_map("assess-clear") is not None

        repo.clear_strategy_map("assess-clear")

        # Post-clear: get returns None, mirroring "no map persisted" state.
        assert repo.get_strategy_map("assess-clear") is None

    @mock_aws
    def test_clear_strategy_map_is_idempotent(self, dynamodb_table):
        """Clearing when no map exists must not raise (idempotent semantics)."""
        repo = DynamoDBAssessmentRepository(dynamodb_table)
        repo.save({"id": "assess-empty", "company_id": "comp-1"})

        # No save_strategy_map call — there's nothing to clear. clear() must succeed.
        repo.clear_strategy_map("assess-empty")
        repo.clear_strategy_map("assess-empty")  # twice, just to be sure

        assert repo.get_strategy_map("assess-empty") is None
