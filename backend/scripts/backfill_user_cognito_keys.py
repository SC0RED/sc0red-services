"""Backfill `cognito_sub`, `GSI1PK`, and `GSI5PK` on legacy user records.

Why this exists
---------------
Two distinct backfill needs converged into one script:

1. **`fix-actor-attribution`** added GSI5 (`COGNITO_SUB#{sub}`) so the
   auth-middleware can resolve `authentication.user_id` to internal
   ids. Pre-existing records lack `GSI5PK` (sparse on day 0) and may
   also lack `cognito_sub` itself if they were registered before that
   field started being tracked.
2. **GSI1PK on user records was missing on legacy data.** Even with
   `org_id` populated, user records written before
   `user_repository.create()` started writing `GSI1PK` / `GSI1SK`
   aren't queryable via `find_by_org` — which broke every actor-name
   lookup in the codebase (Recently Deleted, activity feed, team page).
   This script repairs that gap too.

Discovery via Scan, not GSI1
----------------------------
Earlier draft used `user_repo.find_by_org` to discover users to fix.
That has a chicken-and-egg problem: legacy users lack `GSI1PK`, so
`find_by_org` returns empty, so the script processes zero records.
Switched to a table-scan with `entity_type = "user"` filter, which
finds every user regardless of GSI population. At Janus volumes
(low hundreds of users per org) this is fine; the alternative is
unrecoverable.

Idempotent. Safe to re-run. Records that already have all three
fields set are counted as `already_complete` and skipped.

Required environment
--------------------
  DYNAMODB_TABLE          full table name (e.g. `janus-production`)
  AWS_REGION / AWS_DEFAULT_REGION  matching the table's region
  COGNITO_USER_POOL_ID    pool to look up missing subs against
  AWS_ENDPOINT_URL        set when running against LocalStack

Run from the backend dir
------------------------
  python scripts/backfill_user_cognito_keys.py --org-id ORG --dry-run
  python scripts/backfill_user_cognito_keys.py --org-id ORG --apply

The script is dry-run by default specifically to avoid the
"copy-pasted from a runbook and rewrote production" failure mode.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

import boto3

# Match the path-insert pattern from cleanup_orphan_scans.py so
# `from src.…` resolves when run without `pip install .`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def lookup_cognito_sub_by_email(cognito_client, user_pool_id: str, email: str) -> str | None:
    """Find a Cognito user by email and return their `sub`.

    Returns None when the email isn't registered in the pool — that
    user record is genuinely off-boarded and the script should leave
    it untouched.
    """
    if not email:
        return None
    response = cognito_client.list_users(
        UserPoolId=user_pool_id,
        Filter=f'email = "{email}"',
        Limit=1,
    )
    users = response.get("Users", [])
    if not users:
        return None
    for attribute in users[0].get("Attributes", []):
        if attribute.get("Name") == "sub":
            value = attribute.get("Value", "")
            return value or None
    return None


def discover_users_for_org(
    storage: DynamoDBStorageProvider, org_id: str
) -> list[dict[str, Any]]:
    """Return every user record matching `org_id`, via a table-scan.

    Cannot use `user_repo.find_by_org` because legacy records lack
    `GSI1PK` — the entire reason this script exists. We page through
    the table with `entity_type = "user"` filter and match `org_id`
    in memory.
    """
    table = storage.table._table
    users: list[dict[str, Any]] = []
    last_evaluated_key: dict[str, Any] | None = None
    while True:
        kwargs: dict[str, Any] = {
            "FilterExpression": "entity_type = :t",
            "ExpressionAttributeValues": {":t": "user"},
        }
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key
        response = table.scan(**kwargs)
        users.extend(
            item for item in response.get("Items", []) if item.get("org_id") == org_id
        )
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
    return users


def backfill_org(
    storage: DynamoDBStorageProvider,
    cognito_client,
    user_pool_id: str,
    org_id: str,
    *,
    apply: bool,
) -> dict[str, int]:
    """Walk every user in the org; write `cognito_sub` + GSI1 + GSI5 keys as needed."""
    users = discover_users_for_org(storage, org_id)
    logger.info("found %d users for org_id=%s (scan-based discovery)", len(users), org_id)

    counts = {
        "already_complete": 0,
        "missing_sub_resolved": 0,
        "missing_sub_unresolved": 0,
        "gsi1_added": 0,
        "gsi5_added": 0,
    }

    for user in users:
        user_id = user.get("id", "")
        if not user_id:
            logger.warning("user record without id, skipping: %r", user)
            continue

        existing_sub = user.get("cognito_sub", "")
        has_gsi1 = bool(user.get("GSI1PK"))
        has_gsi5 = bool(user.get("GSI5PK"))

        if existing_sub and has_gsi1 and has_gsi5:
            counts["already_complete"] += 1
            continue

        # Resolve `cognito_sub` if missing — needed for GSI5 keys.
        new_sub = existing_sub
        if not existing_sub:
            email = user.get("email", "")
            new_sub = lookup_cognito_sub_by_email(cognito_client, user_pool_id, email)
            if not new_sub:
                logger.warning(
                    "user_id=%s email=%s — no Cognito record found, skipping sub+GSI5; "
                    "will still attempt GSI1 backfill if missing",
                    user_id,
                    email,
                )
                counts["missing_sub_unresolved"] += 1
            else:
                counts["missing_sub_resolved"] += 1

        updates: dict[str, str] = {}
        if new_sub and not existing_sub:
            updates["cognito_sub"] = new_sub
        if not has_gsi1 and user.get("org_id"):
            # The original gap: legacy records lack GSI1PK so
            # `find_by_org` can't find them. Without this, no actor
            # name resolves anywhere in the app.
            updates["GSI1PK"] = f"ORG#{user['org_id']}"
            updates["GSI1SK"] = f"USER#{user_id}"
            counts["gsi1_added"] += 1
        if new_sub and not has_gsi5:
            updates["GSI5PK"] = f"COGNITO_SUB#{new_sub}"
            updates["GSI5SK"] = f"USER#{user_id}"
            counts["gsi5_added"] += 1

        if not updates:
            continue

        action = "WOULD WRITE" if not apply else "WRITING"
        logger.info("%s user_id=%s updates=%s", action, user_id, list(updates))
        if apply:
            storage.table.update_item(
                pk=f"USER#{user_id}",
                sk="USER#METADATA",
                updates=updates,
            )

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--org-id", required=True, help="Org id to backfill.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write GSI5 + cognito_sub. Default: dry-run.",
    )
    args = parser.parse_args()

    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
    if not user_pool_id:
        logger.error("COGNITO_USER_POOL_ID must be set to look up missing `sub` values.")
        return 1

    cognito_kwargs = {}
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        cognito_kwargs["endpoint_url"] = endpoint_url
    cognito_client = boto3.client("cognito-idp", **cognito_kwargs)

    storage = DynamoDBStorageProvider()
    counts = backfill_org(
        storage,
        cognito_client,
        user_pool_id,
        args.org_id,
        apply=args.apply,
    )

    print(f"\nResults for org {args.org_id}:")
    print(f"  already_complete:        {counts['already_complete']}")
    print(f"  missing_sub_resolved:    {counts['missing_sub_resolved']}")
    print(f"  missing_sub_unresolved:  {counts['missing_sub_unresolved']}  (left untouched)")
    print(f"  gsi1_added:              {counts['gsi1_added']}  (find_by_org now works)")
    print(f"  gsi5_added:              {counts['gsi5_added']}")

    if not args.apply:
        print("\nDry-run mode. Re-run with --apply to write the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
