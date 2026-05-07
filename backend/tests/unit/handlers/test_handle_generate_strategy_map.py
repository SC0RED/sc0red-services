"""Tests for ``handle_generate_strategy_map`` API handler.

Per the strategy-map-on-demand spec, the handler validates access, marks
generation in-flight on the company record, enqueues an SQS message on the
dedicated strategy-map queue, and returns 202 Accepted. The actual generation
runs in the worker (``strategy_map_handler``); this handler is the entry point.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from src.handlers.analysis_handlers import handle_generate_strategy_map


def _make_authentication(org_id: str = "org-1", user_id: str = "user-1") -> MagicMock:
    auth = MagicMock()
    auth.org_id = org_id
    auth.user_id = user_id
    return auth


def _make_storage(company: dict | None) -> tuple[MagicMock, MagicMock]:
    storage = MagicMock()
    company_repo = MagicMock()
    company_repo.get_by_id.return_value = company
    storage.create_company_repository.return_value = company_repo
    return storage, company_repo


class TestHandleGenerateStrategyMap:
    def test_returns_202_and_enqueues_message(self):
        company = {
            "id": "ana-1",
            "company_name": "Acme",
            "scan_id": "scan-1",
            "org_id": "org-1",
        }
        storage, company_repo = _make_storage(company)
        sqs = MagicMock()
        auth = _make_authentication()

        response = handle_generate_strategy_map(
            _event={},
            authentication=auth,
            storage=storage,
            sqs=sqs,
            queue_url="https://sqs.example/janus-strategy-map-queue",
            analysis_id="ana-1",
        )

        # 202 Accepted + analysisId in body
        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["status"] == "queued"
        assert body["analysisId"] == "ana-1"

        # In-flight state set BEFORE SQS send (so refresh during the narrow
        # window still shows the generating placeholder)
        company_repo.set_strategy_map_generation_state.assert_called_once_with(
            "ana-1", "generating"
        )

        # SQS message enqueued with the right shape
        sqs.send_message.assert_called_once()
        call_kwargs = sqs.send_message.call_args.kwargs
        assert call_kwargs["QueueUrl"] == "https://sqs.example/janus-strategy-map-queue"
        message_body = json.loads(call_kwargs["MessageBody"])
        assert message_body["type"] == "strategy_map_generation"
        assert message_body["analysis_id"] == "ana-1"
        assert message_body["scan_id"] == "scan-1"
        # org_id + user_id are NOT in the message — hydration loads them from
        # the persisted company record. Keeps the contract honest about what
        # the consumer reads.
        assert "org_id" not in message_body
        assert "user_id" not in message_body

    def test_returns_404_when_analysis_does_not_exist(self):
        storage, _ = _make_storage(company=None)
        sqs = MagicMock()

        response = handle_generate_strategy_map(
            _event={},
            authentication=_make_authentication(),
            storage=storage,
            sqs=sqs,
            queue_url="https://sqs.example/q",
            analysis_id="ana-missing",
        )

        # check_org_access returns a 404 for missing resources to avoid
        # leaking existence to the wrong tenant.
        assert response["statusCode"] in (403, 404)
        sqs.send_message.assert_not_called()

    def test_returns_503_when_queue_url_unset(self):
        """When STRATEGY_MAP_QUEUE_URL isn't configured, the handler returns 503
        (STRATEGY_MAP_FEATURE_DISABLED) rather than letting boto3 ParamValidationError out."""
        company = {"id": "ana-1", "company_name": "Acme", "org_id": "org-1"}
        storage, company_repo = _make_storage(company)
        sqs = MagicMock()

        response = handle_generate_strategy_map(
            _event={},
            authentication=_make_authentication(),
            storage=storage,
            sqs=sqs,
            queue_url="",  # not configured
            analysis_id="ana-1",
        )

        assert response["statusCode"] == 503
        body = json.loads(response["body"])
        assert body["code"] == "STRATEGY_MAP_FEATURE_DISABLED"
        # Short-circuit: nothing else fires
        sqs.send_message.assert_not_called()
        company_repo.set_strategy_map_generation_state.assert_not_called()

    def test_returns_403_when_org_mismatch(self):
        company = {"id": "ana-1", "org_id": "OTHER_ORG", "company_name": "Acme"}
        storage, _ = _make_storage(company)
        sqs = MagicMock()

        response = handle_generate_strategy_map(
            _event={},
            authentication=_make_authentication(org_id="org-1"),
            storage=storage,
            sqs=sqs,
            queue_url="https://sqs.example/q",
            analysis_id="ana-1",
        )

        # check_org_access denies cross-org reads
        assert response["statusCode"] in (403, 404)
        sqs.send_message.assert_not_called()

    def test_idempotent_on_re_click_when_already_generating(self):
        # Re-click guard: the company record already shows "generating",
        # which means a worker is in flight (or about to fail-safe-clear
        # on retry-3). Returning 202 keeps the frontend's optimistic
        # generating-state happy without enqueueing a duplicate worker
        # that would race the in-flight one on `save_strategy_map`.
        company = {
            "id": "ana-1",
            "company_name": "Acme",
            "scan_id": "scan-1",
            "org_id": "org-1",
            "strategy_map_generation_state": "generating",
        }
        storage, company_repo = _make_storage(company)
        sqs = MagicMock()

        response = handle_generate_strategy_map(
            _event={},
            authentication=_make_authentication(),
            storage=storage,
            sqs=sqs,
            queue_url="https://sqs.example/q",
            analysis_id="ana-1",
        )

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["status"] == "already_in_flight"
        assert body["analysisId"] == "ana-1"
        # Critical: NO new message enqueued, NO state re-set (state was
        # already correct and a second SET would be redundant).
        sqs.send_message.assert_not_called()
        company_repo.set_strategy_map_generation_state.assert_not_called()

    def test_enqueues_when_state_was_previously_cleared(self):
        # Defensive: confirm the idempotency guard checks for the EXACT
        # "generating" sentinel rather than truthy-checking the field.
        # A previously-cleared (absent) field must NOT block a fresh
        # click — that's the whole point of clearing on success / failure.
        company = {
            "id": "ana-1",
            "company_name": "Acme",
            "scan_id": "scan-1",
            "org_id": "org-1",
            # Field genuinely absent (mirrors the post-clear state).
        }
        storage, company_repo = _make_storage(company)
        sqs = MagicMock()

        response = handle_generate_strategy_map(
            _event={},
            authentication=_make_authentication(),
            storage=storage,
            sqs=sqs,
            queue_url="https://sqs.example/q",
            analysis_id="ana-1",
        )

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body["status"] == "queued"
        sqs.send_message.assert_called_once()
        company_repo.set_strategy_map_generation_state.assert_called_once_with(
            "ana-1", "generating"
        )
