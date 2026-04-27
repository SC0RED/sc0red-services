"""Analytics event handler — validates client envelope, enriches with JWT identity, logs.

This handler is the thin glue between the frontend's typed emit helpers and
the CloudWatch Logs sink. It does three things and nothing else:

1. Parse + validate the client-submitted envelope via Pydantic. Any
   validation failure becomes a 400 and nothing is logged.
2. Build an ``EnrichedAnalyticsEvent`` by layering the authenticated
   JWT's ``user_id`` and ``org_id`` on top of the envelope. Anti-spoofing
   is structural: ``AnalyticsEvent`` uses ``extra="forbid"``, so a
   client body carrying ``user_id`` / ``org_id`` fails validation with
   a 400 before we ever reach this line.
3. Hand the enriched event to the CloudWatch sink and return 202.

The 202 status is deliberate — "accepted, will be processed" matches the
asynchronous nature of log-based analytics (the event is durably
persisted to CloudWatch before we respond, but downstream Logs Insights
queries happen later).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from src.handlers.api_gateway_handler import (
    VALIDATION_ERROR,
    build_error,
    build_json_response,
)
from src.models.analytics_events import AnalyticsEvent, EnrichedAnalyticsEvent
from src.utilities.analytics_logger import emit_event

if TYPE_CHECKING:
    from src.handlers.api_gateway_handler import LambdaResponse
    from src.handlers.auth_middleware import AuthContext

logger = logging.getLogger(__name__)


def handle_post_event(
    event: dict[str, Any],
    authentication: AuthContext,
) -> LambdaResponse:
    """Handle POST /api/analytics/events.

    Validates the client event envelope, enriches with authenticated
    identity, and persists to CloudWatch Logs. The handler does NOT use
    the DynamoDB storage provider — analytics events never touch the
    operational database — which is why the signature omits the
    ``storage`` parameter other handlers take.
    """
    raw_body = event.get("body") or "{}"
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as error:
        return build_error(f"Invalid JSON: {error}", 400, VALIDATION_ERROR)

    try:
        client_event = AnalyticsEvent.model_validate(body)
    except ValidationError as error:
        # Pydantic's error output is structured and safe to surface —
        # the frontend uses it to log in dev builds.
        return build_error(f"Invalid analytics event: {error}", 400, VALIDATION_ERROR)

    enriched = EnrichedAnalyticsEvent.from_client_event(
        client_event,
        user_id=authentication.user_id,
        org_id=authentication.org_id,
    )

    emit_event(enriched)

    logger.info(
        "analytics event accepted: event_type=%s analysis_id=%s org_id=%s",
        enriched.event_type,
        enriched.analysis_id,
        enriched.org_id,
    )
    return build_json_response({"accepted": True}, status=202)
