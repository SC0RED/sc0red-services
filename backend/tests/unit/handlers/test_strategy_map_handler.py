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


def _make_message(
    analysis_id: str = "ana-1",
    scan_id: str = "scan-1",
    *,
    receive_count: int = 1,
) -> dict[str, Any]:
    """Build an SQS event with a single strategy-map-generation message.

    ``receive_count`` mirrors the real SQS ``ApproximateReceiveCount``
    attribute — set to the queue's ``max_receive_count`` (3) to simulate
    the final retry attempt before DLQ.
    """
    body = json.dumps(
        {
            "type": "strategy_map_generation",
            "analysis_id": analysis_id,
            "org_id": "org-1",
            "user_id": "user-1",
            "scan_id": scan_id,
        }
    )
    return {
        "Records": [
            {
                "messageId": "msg-1",
                "body": body,
                "attributes": {"ApproximateReceiveCount": str(receive_count)},
            }
        ]
    }


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


class TestStrategyMapSQSHandlerFailSafeCleanup:
    """Last-retry fail-safe: clear stuck ``generating`` state + notify failure
    so the user isn't permanently stuck on the spinner when a programming
    error blows past max_receive_count and the message lands in the DLQ.
    """

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_failed")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    def test_first_retry_attempt_does_not_trigger_fail_safe(
        self,
        mock_hydrate: MagicMock,
        mock_notify_failed: MagicMock,
    ):
        # Receive count 1 — there are still retries left, so the worker
        # should NOT clear state or notify failure. The user keeps seeing
        # the generating placeholder while SQS retries.
        storage, company_repo, _ = _make_storage()
        mock_hydrate.side_effect = KeyError("unexpectedly missing field")

        handler = StrategyMapSQSHandler(storage, MagicMock())
        result = handler.handle(_make_message(receive_count=1))

        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-1"}]}
        company_repo.clear_strategy_map_generation_state.assert_not_called()
        mock_notify_failed.assert_not_called()

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_failed")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    def test_intermediate_retry_attempt_does_not_trigger_fail_safe(
        self,
        mock_hydrate: MagicMock,
        mock_notify_failed: MagicMock,
    ):
        # Boundary check: receive count 2 (not yet at max=3). An
        # off-by-one in the comparison (e.g. ``> _MAX_RECEIVE_COUNT - 1``
        # instead of ``>= _MAX_RECEIVE_COUNT``) would clear state too
        # early, releasing the slot to the CTA while a retry is still
        # in flight — this test pins the inequality.
        storage, company_repo, _ = _make_storage()
        mock_hydrate.side_effect = KeyError("unexpectedly missing field")

        handler = StrategyMapSQSHandler(storage, MagicMock())
        result = handler.handle(_make_message(receive_count=2))

        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-1"}]}
        company_repo.clear_strategy_map_generation_state.assert_not_called()
        mock_notify_failed.assert_not_called()

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_failed")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    def test_final_retry_attempt_clears_state_and_notifies_failure(
        self,
        mock_hydrate: MagicMock,
        mock_notify_failed: MagicMock,
    ):
        # Receive count 3 = max_receive_count. The message is going to
        # the DLQ regardless of what we return. Run the fail-safe cleanup
        # so the company record's "generating" marker is cleared and the
        # frontend's strategy-map slot returns to the CTA state.
        storage, company_repo, _ = _make_storage()
        mock_hydrate.side_effect = KeyError("unexpectedly missing field")

        handler = StrategyMapSQSHandler(storage, MagicMock())
        result = handler.handle(_make_message(receive_count=3))

        # Still surfaces to batchItemFailures — SQS routes to DLQ regardless,
        # but signaling here keeps the message-ack contract correct so SQS
        # doesn't accidentally treat the record as a successful consume.
        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-1"}]}
        company_repo.clear_strategy_map_generation_state.assert_called_once_with("ana-1")
        mock_notify_failed.assert_called_once()
        notify_kwargs = mock_notify_failed.call_args.kwargs
        assert notify_kwargs["analysis_id"] == "ana-1"
        assert notify_kwargs["scan_id"] == "scan-1"
        assert "retry limit" in notify_kwargs["error_message"].lower()

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_failed")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    def test_fail_safe_swallows_its_own_errors(
        self,
        mock_hydrate: MagicMock,
        mock_notify_failed: MagicMock,
    ):
        # The fail-safe MUST NOT mask the original programming error. If
        # the cleanup itself errors (DynamoDB outage, AppSync down), we
        # log + drop on the floor — the message still goes to the DLQ
        # and ops gets the original programming-error stacktrace.
        storage, company_repo, _ = _make_storage()
        mock_hydrate.side_effect = KeyError("unexpectedly missing field")
        company_repo.clear_strategy_map_generation_state.side_effect = RuntimeError(
            "DynamoDB throttled"
        )

        handler = StrategyMapSQSHandler(storage, MagicMock())
        # Must NOT raise — fail-safe internal failure is contained.
        result = handler.handle(_make_message(receive_count=3))

        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-1"}]}

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_failed")
    def test_fail_safe_skips_when_message_body_lacks_analysis_id(
        self,
        mock_notify_failed: MagicMock,
    ):
        # A malformed message that survived JSON-parsing but is missing
        # the required ``analysis_id`` field should not blow up the
        # cleanup path — there's nothing to clear, log + skip.
        storage, company_repo, _ = _make_storage()

        handler = StrategyMapSQSHandler(storage, MagicMock())
        bad_event = {
            "Records": [
                {
                    "messageId": "msg-bad",
                    "body": json.dumps({"type": "strategy_map_generation"}),
                    "attributes": {"ApproximateReceiveCount": "3"},
                }
            ]
        }
        result = handler.handle(bad_event)

        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-bad"}]}
        company_repo.clear_strategy_map_generation_state.assert_not_called()
        mock_notify_failed.assert_not_called()


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


class TestStrategyMapSQSHandlerCheckpointLogging:
    """The strategy-map worker must emit OUTER-level checkpoint logs at
    each stage so CloudWatch shows progress even if the
    ``executor.execute_all()`` inner chain's logs are eaten by a runtime
    quirk. Mirrors the analysis worker's
    ``sqs_handler.handle_async_analysis`` pattern.

    Tests assert via ``patch.object(logger, "info")`` rather than
    pytest's ``caplog`` because the autouse fixtures in this directory's
    ``conftest.py`` (``mock_ai_client_factory`` etc.) interfere with
    pytest-cov's logger interception, leaving caplog empty. Patching
    the module-level logger directly is the same boundary check
    without the plugin interaction.
    """

    @staticmethod
    def _make_happy_company(
        *,
        risk_count: int = 2,
        opp_count: int = 3,
        ebitda: bool = True,
        value_chain: bool = False,
    ) -> MagicMock:
        company = MagicMock()
        company.profile = MagicMock()
        company.risk_assessment = MagicMock()
        company.risk_assessment.risk_scores = [MagicMock() for _ in range(risk_count)]
        company.opportunity_result = MagicMock()
        company.opportunity_result.opportunities = [MagicMock() for _ in range(opp_count)]
        company.ebitda_tree = MagicMock() if ebitda else None
        company.value_chain = MagicMock() if value_chain else None
        company.strategy_map = MagicMock()
        company.strategy_map.model_dump.return_value = {"vision": {"statement": "v"}}
        return company

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_complete")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    @patch("src.handlers.strategy_map_handler.GenerateStrategyMap")
    @patch("src.handlers.strategy_map_handler.logger")
    def test_emits_processing_log_at_message_start(
        self,
        mock_logger: MagicMock,
        mock_step_class: MagicMock,
        mock_hydrate: MagicMock,
        mock_notify_complete: MagicMock,
    ):
        storage, _, assessment_repo = _make_storage()
        mock_hydrate.return_value = self._make_happy_company()
        mock_step_class.return_value = MagicMock()
        assessment_repo.find_by_company.return_value = [
            {"id": "assess-1", "created_at": "2026-01-01T00:00:00Z"}
        ]

        handler = StrategyMapSQSHandler(storage, MagicMock())
        handler.handle(_make_message(analysis_id="ana-77", scan_id="scan-77"))

        processing_calls = [
            call
            for call in mock_logger.info.call_args_list
            if "Processing strategy-map" in (call.args[0] if call.args else "")
        ]
        assert len(processing_calls) == 1
        # Args 1 + 2 of the format-style logger.info call: analysis_id, scan_id.
        assert processing_calls[0].args[1] == "ana-77"
        assert processing_calls[0].args[2] == "scan-77"

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_complete")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    @patch("src.handlers.strategy_map_handler.GenerateStrategyMap")
    @patch("src.handlers.strategy_map_handler.logger")
    def test_emits_hydration_summary_with_shape_facts(
        self,
        mock_logger: MagicMock,
        mock_step_class: MagicMock,
        mock_hydrate: MagicMock,
        mock_notify_complete: MagicMock,
    ):
        # The hydration summary log shows the prerequisite-data counts
        # so a future hydration regression (missing risk scores, missing
        # opportunities) surfaces in CloudWatch as low values rather
        # than only as a downstream ValidationError.
        storage, _, assessment_repo = _make_storage()
        mock_hydrate.return_value = self._make_happy_company(
            risk_count=7, opp_count=5, ebitda=True, value_chain=True
        )
        mock_step_class.return_value = MagicMock()
        assessment_repo.find_by_company.return_value = [
            {"id": "assess-1", "created_at": "2026-01-01T00:00:00Z"}
        ]

        handler = StrategyMapSQSHandler(storage, MagicMock())
        handler.handle(_make_message(analysis_id="ana-9"))

        hydration_calls = [
            call
            for call in mock_logger.info.call_args_list
            if "Hydrated company for strategy-map" in (call.args[0] if call.args else "")
        ]
        assert len(hydration_calls) == 1
        # Args ordering of the format-style logger.info call:
        #   1: analysis_id, 2: profile_present, 3: risk_count,
        #   4: opp_count, 5: ebitda_present, 6: value_chain_present.
        args = hydration_calls[0].args
        assert args[1] == "ana-9"
        assert args[2] is True  # profile_present
        assert args[3] == 7  # risk_scores
        assert args[4] == 5  # opportunities
        assert args[5] is True  # ebitda_present
        assert args[6] is True  # value_chain_present

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_complete")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    @patch("src.handlers.strategy_map_handler.GenerateStrategyMap")
    @patch("src.handlers.strategy_map_handler.logger")
    def test_emits_persist_and_completion_logs(
        self,
        mock_logger: MagicMock,
        mock_step_class: MagicMock,
        mock_hydrate: MagicMock,
        mock_notify_complete: MagicMock,
    ):
        # Persist log includes the assessment_id so ops can cross-check
        # DynamoDB. Completion log includes wall-clock seconds so a
        # regression where the worker quietly takes 10x longer is
        # immediately visible in CloudWatch.
        storage, _, assessment_repo = _make_storage()
        mock_hydrate.return_value = self._make_happy_company(risk_count=1, opp_count=1)
        mock_step_class.return_value = MagicMock()
        assessment_repo.find_by_company.return_value = [
            {"id": "assess-77", "created_at": "2026-01-01T00:00:00Z"}
        ]

        handler = StrategyMapSQSHandler(storage, MagicMock())
        handler.handle(_make_message(analysis_id="ana-77", scan_id="scan-77"))

        persist_calls = [
            call
            for call in mock_logger.info.call_args_list
            if "Persisted strategy map" in (call.args[0] if call.args else "")
        ]
        assert len(persist_calls) == 1
        assert persist_calls[0].args[1] == "ana-77"
        assert persist_calls[0].args[2] == "assess-77"

        completion_calls = [
            call
            for call in mock_logger.info.call_args_list
            if "Strategy-map generation complete" in (call.args[0] if call.args else "")
        ]
        assert len(completion_calls) == 1
        assert completion_calls[0].args[1] == "ana-77"
        assert completion_calls[0].args[2] == "scan-77"
        # The fourth %s/%-format arg is the elapsed seconds float.
        elapsed = completion_calls[0].args[3]
        assert isinstance(elapsed, float)
        assert elapsed >= 0

    @patch("src.handlers.strategy_map_handler.notify_strategy_map_failed")
    @patch("src.handlers.strategy_map_handler.hydrate_company_for_strategy_map")
    @patch("src.handlers.strategy_map_handler.logger")
    def test_processing_log_fires_even_on_hydration_failure(
        self,
        mock_logger: MagicMock,
        mock_hydrate: MagicMock,
        mock_notify_failed: MagicMock,
    ):
        # The "Processing strategy-map …" log MUST fire BEFORE
        # _generate_and_persist runs — otherwise a hydration failure
        # would produce a CloudWatch view with zero "we got the message"
        # markers, masking the worker's behavior. Pin that the log
        # appears even when downstream blows up.
        storage, _, _ = _make_storage()
        mock_hydrate.side_effect = StrategyMapHydrationError("missing assessment")

        handler = StrategyMapSQSHandler(storage, MagicMock())
        handler.handle(_make_message(analysis_id="ana-fail"))

        processing_calls = [
            call
            for call in mock_logger.info.call_args_list
            if "Processing strategy-map" in (call.args[0] if call.args else "")
        ]
        assert len(processing_calls) == 1

        # Hydration + completion logs MUST NOT fire on the failure path.
        hydration_calls = [
            call
            for call in mock_logger.info.call_args_list
            if "Hydrated company" in (call.args[0] if call.args else "")
        ]
        completion_calls = [
            call
            for call in mock_logger.info.call_args_list
            if "Strategy-map generation complete" in (call.args[0] if call.args else "")
        ]
        assert hydration_calls == []
        assert completion_calls == []
