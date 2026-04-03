"""SQS polling worker for local / E2E integration testing.

Polls an SQS queue and dispatches messages to SQSHandler, mirroring
what the Lambda SQS trigger does in production.

Usage (from the backend container or local venv):
    python scripts/sqs_worker.py

Required environment variables:
    ANALYSIS_QUEUE_URL  — full SQS queue URL
    AWS_REGION          — default us-east-1
    AWS_ENDPOINT_URL    — set to LocalStack URL for local testing
"""

from __future__ import annotations

import logging
import os
import sys
import time

import boto3

# In Docker the package is installed via `pip install .`, making `src` importable
# directly. However, when running locally with `python scripts/sqs_worker.py`
# from the backend directory without installing the package, the parent directory
# must be on sys.path so that `from src.…` resolves correctly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.handlers.sqs_handler import SQSHandler  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

_QUEUE_URL = os.environ["ANALYSIS_QUEUE_URL"]
_WAIT_TIME_SECONDS = 5
_MAX_MESSAGES = 10
_RETRY_SLEEP_SECONDS = 2

_sqs = boto3.client(
    "sqs",
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "local"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "local"),
    endpoint_url=os.environ.get("AWS_ENDPOINT_URL"),
)

_handler = SQSHandler()


def _poll_once() -> None:
    response = _sqs.receive_message(
        QueueUrl=_QUEUE_URL,
        MaxNumberOfMessages=_MAX_MESSAGES,
        WaitTimeSeconds=_WAIT_TIME_SECONDS,
    )
    messages = response.get("Messages", [])
    if not messages:
        return

    logger.info("Received %d message(s)", len(messages))

    event = {
        "Records": [
            {"messageId": message["MessageId"], "body": message["Body"]}
            for message in messages
        ]
    }
    result = _handler.handle(event)
    failures = {failure["itemIdentifier"] for failure in result.get("batchItemFailures", [])}

    for message in messages:
        if message["MessageId"] not in failures:
            _sqs.delete_message(
                QueueUrl=_QUEUE_URL,
                ReceiptHandle=message["ReceiptHandle"],
            )
            logger.info("Deleted message %s", message["MessageId"])
        else:
            logger.warning("Message %s failed — leaving on queue", message["MessageId"])


if __name__ == "__main__":
    logger.info("SQS worker started — queue: %s", _QUEUE_URL)
    while True:
        try:
            _poll_once()
        except Exception:
            logger.exception("Error during poll")
            time.sleep(_RETRY_SLEEP_SECONDS)
