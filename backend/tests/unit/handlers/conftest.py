"""Shared fixtures for handler unit tests."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_ai_client_factory():
    """Patch AI client factory initialization for all handler tests.

    Handler tests construct real handler instances (APIGatewayHandler, SQSHandler,
    FactoryManager) that trigger the AI initialization chain. The AI provider and
    API keys are not a concern in handler unit tests — they are tested separately
    in test_factories_factory.py.
    """
    with patch(
        "src.pipeline.factories_factory._initialize_ai_client_factory",
        return_value=MagicMock(),
    ):
        yield
