"""Shared fixtures for handler unit tests."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_ai_client_factory():
    """Patch AI client factory initialization for all handler tests."""
    with patch(
        "src.pipeline.factories_factory._initialize_ai_client_factory",
        return_value=MagicMock(),
    ):
        yield


@pytest.fixture(autouse=True)
def analysis_queue_url(monkeypatch):
    """Provide ANALYSIS_QUEUE_URL env var required by APIGatewayHandler.__init__."""
    monkeypatch.setenv("ANALYSIS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/test-queue")


@pytest.fixture(autouse=True)
def mock_boto3_sqs():
    """Patch boto3.client so APIGatewayHandler.__init__ does not create a real SQS client."""
    with patch("src.handlers.api_gateway_handler.boto3") as mock_boto3:
        mock_boto3.client.return_value = MagicMock()
        yield mock_boto3
