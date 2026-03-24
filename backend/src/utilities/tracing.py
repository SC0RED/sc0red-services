"""X-Ray tracing setup — patches boto3 and httpx when running in Lambda.

Only activates when ``AWS_XRAY_DAEMON_ADDRESS`` is set by the Lambda runtime
(injected automatically when ``lambda_.Tracing.ACTIVE`` is configured in CDK).
In local development and tests, the environment variable is absent, so this
module is a no-op.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def configure_tracing() -> None:
    """Patch AWS SDK clients for X-Ray if the X-Ray daemon is available.

    Called once at module level in Lambda handler entry points.  The patches
    wrap boto3 and httpx to emit X-Ray subsegments for every DynamoDB query,
    SQS send, and outbound HTTP call (including AI provider requests).

    MUST be called before any boto3 resource or client is created — the
    botocore patch only intercepts sessions created after ``patch()`` runs.
    """
    if not os.environ.get("AWS_XRAY_DAEMON_ADDRESS"):
        return

    from aws_xray_sdk.core import patch

    patch(["boto3", "httpx"])
    logger.info("X-Ray tracing enabled — patched boto3 and httpx")
