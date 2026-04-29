"""Backfill `cognito_sub` and `GSI5PK` on legacy user records.

Why this exists
---------------
The `fix-actor-attribution` change adds GSI5 (`COGNITO_SUB#{sub}`) so
the auth-middleware can translate `authentication.user_id` from the
JWT's `sub` to the internal `user["id"]`. Records written via the
existing register flow already store `cognito_sub` as a plain
attribute, but:

  1. Records registered before the field was tracked don't have
     `cognito_sub` at all.
  2. Even records that have `cognito_sub` lack `GSI5PK` / `GSI5SK`
     until they are explicitly written (the GSI is sparse on day 0).

This script repairs both. It pages through every user record (via
GSI1 by org), resolves the missing `cognito_sub` from Cognito by
email if needed, and writes `GSI5PK` + `GSI5SK` so the record becomes
queryable via `find_by_cognito_sub`.

Idempotent. Safe to re-run.

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


def backfill_org(
    storage: DynamoDBStorageProvider,
    cognito_client,
    user_pool_id: str,
    org_id: str,
    *,
    apply: bool,
) -> dict[str, int]:
    """Walk every user in the org; write `cognito_sub` + GSI5 keys as needed."""
    user_repo = storage.create_user_repository()
    users = user_repo.find_by_org(org_id)
    logger.info("scanning %d users for org_id=%s", len(users), org_id)

    counts = {
        "already_complete": 0,
        "missing_sub_resolved": 0,
        "missing_sub_unresolved": 0,
        "gsi5_added": 0,
    }

    for user in users:
        user_id = user.get("id", "")
        if not user_id:
            logger.warning("user record without id, skipping: %r", user)
            continue

        existing_sub = user.get("cognito_sub", "")
        has_gsi5 = bool(user.get("GSI5PK"))

        if existing_sub and has_gsi5:
            counts["already_complete"] += 1
            continue

        new_sub = existing_sub
        if not existing_sub:
            email = user.get("email", "")
            new_sub = lookup_cognito_sub_by_email(cognito_client, user_pool_id, email)
            if not new_sub:
                logger.warning(
                    "user_id=%s email=%s — no Cognito record found, skipping",
                    user_id,
                    email,
                )
                counts["missing_sub_unresolved"] += 1
                continue
            counts["missing_sub_resolved"] += 1

        updates: dict[str, str] = {}
        if not existing_sub:
            updates["cognito_sub"] = new_sub
        if not has_gsi5:
            updates["GSI5PK"] = f"COGNITO_SUB#{new_sub}"
            updates["GSI5SK"] = f"USER#{user_id}"

        action = "WOULD WRITE" if not apply else "WRITING"
        logger.info("%s user_id=%s updates=%s", action, user_id, list(updates))
        if apply:
            storage.table.update_item(
                pk=f"USER#{user_id}",
                sk="USER#METADATA",
                updates=updates,
            )
        counts["gsi5_added"] += 1

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
    print(f"  gsi5_added:              {counts['gsi5_added']}")

    if not args.apply:
        print("\nDry-run mode. Re-run with --apply to write the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
