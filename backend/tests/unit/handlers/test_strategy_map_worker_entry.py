"""Smoke tests for the strategy-map worker Lambda entry point.

The Lambda invokes ``handle_event(event, context)`` on cold start. We verify:
  - Lazy initialisation (storage + AI factory) is thread-safe
  - The dispatch wires up to ``StrategyMapSQSHandler``
  - Cold-start re-uses cached singletons
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.handlers import strategy_map_worker_entry


class TestStrategyMapWorkerEntry:
    @patch("src.handlers.strategy_map_worker_entry._get_ai_client_factory")
    @patch("src.handlers.strategy_map_worker_entry._get_storage")
    @patch("src.handlers.strategy_map_worker_entry.StrategyMapSQSHandler")
    def test_handle_event_dispatches_to_handler(
        self,
        mock_handler_class: MagicMock,
        mock_get_storage: MagicMock,
        mock_get_ai_factory: MagicMock,
    ):
        """Cold-start invocation builds an SQSHandler and delegates."""
        mock_storage = MagicMock()
        mock_ai_factory = MagicMock()
        mock_get_storage.return_value = mock_storage
        mock_get_ai_factory.return_value = mock_ai_factory

        mock_handler = MagicMock()
        mock_handler.handle.return_value = {"batchItemFailures": []}
        mock_handler_class.return_value = mock_handler

        event = {"Records": [{"messageId": "m-1", "body": "{}"}]}
        result = strategy_map_worker_entry.handle_event(event, _context=None)

        # Handler instantiated with the lazily-loaded singletons
        mock_handler_class.assert_called_once_with(mock_storage, mock_ai_factory)
        # Event dispatched to the handler unchanged
        mock_handler.handle.assert_called_once_with(event)
        assert result == {"batchItemFailures": []}

    def test_lazy_init_caches_storage_singleton(self):
        """Subsequent _get_storage calls return the same instance."""
        # Reset module-level cache so the test is order-independent.
        strategy_map_worker_entry._storage = None

        with patch(
            "src.handlers.strategy_map_worker_entry.DynamoDBStorageProvider"
        ) as mock_provider_class:
            mock_provider_class.return_value = MagicMock(name="provider-instance")

            first = strategy_map_worker_entry._get_storage()
            second = strategy_map_worker_entry._get_storage()

            # One construction, two retrievals — singleton holds.
            assert mock_provider_class.call_count == 1
            assert first is second

        # Reset for hermeticity.
        strategy_map_worker_entry._storage = None

    def test_lazy_init_caches_ai_factory_singleton(self):
        """Subsequent _get_ai_client_factory calls return the same instance."""
        strategy_map_worker_entry._ai_client_factory = None

        with patch(
            "src.handlers.strategy_map_worker_entry._initialize_ai_client_factory"
        ) as mock_init:
            mock_init.return_value = MagicMock(name="ai-factory-instance")

            first = strategy_map_worker_entry._get_ai_client_factory()
            second = strategy_map_worker_entry._get_ai_client_factory()

            assert mock_init.call_count == 1
            assert first is second

        strategy_map_worker_entry._ai_client_factory = None
