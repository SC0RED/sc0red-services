"""Tests for the on-demand strategy-map SQS worker.

Covers the three failure modes from the strategy-map-on-demand spec:
- Happy path: hydrate → generate → persist → notify_strategy_map_complete
- Domain error: AppSync notify_strategy_map_failed + state cleared, NOT retried
- Programming error: surfaces to SQS batch_item_failures for retry
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.handlers._strategy_map_hydration import StrategyMapHydrationError
from src.handlers.strategy_map_handler import StrategyMapSQSHandler


def _make_message(analysis_id: str = "ana-1", scan_id: str = "scan-1") -> dict[str, Any]:
    """Build an SQS event with a single strategy-map-generation message."""
    body = json.dumps(
        {
            "type": "strategy_map_generation",
            "analysis_id": analysis_id,
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": scan_id,
        }
    )
    return {"Records": [{"messageId": "msg-1", "body": body}]}


def _make_storage() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Build a storage stub with company + assessment repos as MagicMocks."""
    storage = MagicMock()
    company_repo = MagicMock()
    assessment_repo = MagicMock()
    storage.create_company_repository.return_value = company_repo
    storage.create_assessment_repository.return_value = assessment_repo
    return storage, company_repo, assessment_repo


class TestStrategyMapSQSHandlerHappyPath:
    @patch("src.handlers.strategy_map_handler.notify_strategy_map_complete")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    @patch("src.handlers.strategy_map_handler.GenerateStrategyMap")
    def test_complete_flow_persists_and_notifies(
        self,
        mock_step_class: MagicMock,
        mock_hydrate: MagicMock,
        mock_notify_complete: MagicMock,
    ):
        storage, company_repo, assessment_repo = _make_storage()
        ai_factory = MagicMock()

        # Hydration returns a Company-shaped object whose strategy_map will be
        # populated by the step's execute().
        company = MagicMock()
        company.strategy_map = MagicMock()
        company.strategy_map.model_dump.return_value = {"vision": {"statement": "v"}}
        mock_hydrate.return_value = company

        # The step's execute() is what writes to accessor.company.strategy_map
        # in the real path; we simulate that by leaving the mock company's
        # strategy_map already non-None.
        mock_step = MagicMock()
        mock_step_class.return_value = mock_step

        # Most-recent assessment lookup
        assessment_repo.find_by_company.return_value = [
            {"id": "assess-1", "created_at": "2026-01-01T00:00:00Z"}
        ]

        handler = StrategyMapSQSHandler(storage, ai_factory)
        result = handler.handle(_make_message())

        assert result == {"batchItemFailures": []}
        # Generation step was wired and run
        mock_step_class.assert_called_once_with(ai_client_factory=ai_factory)
        mock_step.execute.assert_called_once()
        # Strategy map persisted under the latest assessment id
        assessment_repo.save_strategy_map.assert_called_once()
        save_args = assessment_repo.save_strategy_map.call_args
        assert save_args.args[0] == "assess-1"
        # In-flight state cleared
        company_repo.clear_strategy_map_generation_state.assert_called_once_with("ana-1")
        # AppSync push fired
        mock_notify_complete.assert_called_once_with(scan_id="scan-1", analysis_id="ana-1")


class TestStrategyMapSQSHandlerDomainError:
    @patch("src.handlers.strategy_map_handler.notify_strategy_map_failed")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    def test_hydration_error_emits_failure_and_clears_state(
        self, mock_hydrate: MagicMock, mock_notify_failed: MagicMock
    ):
        """Domain error → AppSync notify_failed + state cleared + SQS success.

        SQS does NOT retry — the user clicks "Generate" again to retry.
        """
        storage, company_repo, _assessment_repo = _make_storage()
        mock_hydrate.side_effect = StrategyMapHydrationError(
            "Cannot hydrate: analysis ana-7 has no assessment record"
        )

        handler = StrategyMapSQSHandler(storage, MagicMock())
        result = handler.handle(_make_message(analysis_id="ana-7"))

        # Empty batchItemFailures = SQS treats record as successfully processed.
        assert result == {"batchItemFailures": []}
        # State cleared so the CTA returns
        company_repo.clear_strategy_map_generation_state.assert_called_once_with("ana-7")
        # Failure event pushed; the original error_message is logged but the
        # AppSync payload uses generic copy (covered by appsync_notifier tests).
        mock_notify_failed.assert_called_once()
        kwargs = mock_notify_failed.call_args.kwargs
        assert kwargs["analysis_id"] == "ana-7"

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_failed")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    def test_value_error_during_generation_is_treated_as_domain_error(
        self, mock_hydrate: MagicMock, mock_notify_failed: MagicMock
    ):
        """ValueError from generation (e.g., missing prerequisite) → failure event."""
        storage, company_repo, _ = _make_storage()
        mock_hydrate.side_effect = ValueError(
            "Cannot generate strategy map: company profile missing"
        )

        handler = StrategyMapSQSHandler(storage, MagicMock())
        result = handler.handle(_make_message())

        assert result == {"batchItemFailures": []}
        mock_notify_failed.assert_called_once()
        company_repo.clear_strategy_map_generation_state.assert_called_once()


class TestStrategyMapSQSHandlerProgrammingError:
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    def test_programming_error_surfaces_to_batch_item_failures(self, mock_hydrate: MagicMock):
        """KeyError / TypeError / AttributeError → SQS retry, not silent consumption."""
        storage, _, _ = _make_storage()
        mock_hydrate.side_effect = KeyError("unexpectedly missing field")

        handler = StrategyMapSQSHandler(storage, MagicMock())
        result = handler.handle(_make_message())

        # Programming error → record retries via batchItemFailures
        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-1"}]}


class TestStrategyMapSQSHandlerMessageDispatch:
    def test_unexpected_message_type_raises(self):
        """Defensive: messages with the wrong type discriminator must not
        silently no-op. They surface via batchItemFailures so ops sees them."""
        storage, _, _ = _make_storage()
        handler = StrategyMapSQSHandler(storage, MagicMock())

        bad_event = {
            "Records": [
                {
                    "messageId": "msg-bad",
                    "body": json.dumps({"type": "wrong_type", "analysis_id": "x"}),
                }
            ]
        }
        # The ValueError from the type-check is a "domain" error from the
        # outer try's perspective — but it doesn't match the EngineError /
        # ValueError / RuntimeError / StrategyMapHydrationError catch because
        # the type-check happens BEFORE the try block in _process_message.
        # Wait — looking again, the type check is at the top of _process_message
        # OUTSIDE the try, so the ValueError propagates to handle()'s broad
        # except, which puts it in batchItemFailures. Verify that behaviour.
        result = handler.handle(bad_event)
        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-bad"}]}


@pytest.fixture
def _verify_storage_unused() -> None:
    """Smoke check that the test setup helper builds a callable storage stub."""
    storage, company_repo, assessment_repo = _make_storage()
    assert storage.create_company_repository() is company_repo
    assert storage.create_assessment_repository() is assessment_repo
