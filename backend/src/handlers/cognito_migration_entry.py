"""Lambda entry point for the Cognito User Migration trigger.

Separate from the main API/Worker Lambdas to keep cold start small
(only needs DynamoDB + bcrypt, not the full AI pipeline).
"""

from __future__ import annotations

import logging
from typing import Any

from src.handlers.cognito_migration_trigger import handle_migration
from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_storage = DynamoDBStorageProvider()


def handle_migration_event(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambda handler for Cognito UserMigration trigger."""
    logger.info(
        "Migration Lambda invoked: trigger=%s user=%s",
        event.get("triggerSource"),
        event.get("userName"),
    )
    user_repo = _storage.create_user_repository()
    return handle_migration(event, user_repo)
