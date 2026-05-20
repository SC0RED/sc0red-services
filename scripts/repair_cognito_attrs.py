#!/usr/bin/env python3
"""Repair Cognito custom attributes on existing users after a botched migration.

The ``janus → sc0red-services`` rename runbook
(``docs/janus-to-sc0red-services-aws-migration.md``) originally created new
Cognito users with only ``email`` + ``email_verified``, omitting the
``custom:org_id`` / ``custom:role`` / ``custom:legacy_user_id`` attributes
the backend's auth middleware requires. The runbook has since been
patched, but pools created under the old runbook will still have users
with no custom attributes — every authenticated API call returns 401
``Token missing required org_id claim`` until the attributes are
backfilled.

This script reads each user's historic ``org_id`` / ``role`` / ``id``
from the DynamoDB user record (via GSI4 = ``EMAIL#``) and stamps the
two mutable custom attributes onto the corresponding Cognito user.

What this script CANNOT do
--------------------------
``custom:legacy_user_id`` is declared **immutable** in the Cognito pool
schema (see ``cognito_construct.py``). Cognito refuses
``admin-update-user-attributes`` for immutable attributes once the user
exists, and the whole call aborts atomically if any single attribute is
unupdatable. So:

  - Users created WITH ``custom:legacy_user_id`` set at create-time → fine,
    nothing to repair on that field.
  - Users created WITHOUT it → the field is permanently unsettable on
    that user record. Login still works because the auth middleware's
    user-resolution chain falls through to ``find_by_email``, but the
    DDB user record's ``cognito_sub`` should also be backfilled so the
    primary ``find_by_cognito_sub`` path matches.

The script also backfills ``cognito_sub`` + ``GSI5PK`` on the DDB user
record when the new Cognito sub differs from the persisted one.

Usage
-----
::

    AWS_PROFILE=sc0red-dev \\
    AWS_REGION=us-east-1 \\
    python scripts/repair_cognito_attrs.py \\
        --user-pool-id us-east-1_JT4ly5noc \\
        --table sc0red-services-staging \\
        --email vedratna.velani@sc0red.com \\
        --email zack.walmer@sc0red.com

Pass ``--dry-run`` to print what would happen without mutating anything.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import boto3

# Custom attributes the backend's auth middleware reads. Mutable post-
# creation are listed first; the immutable ``legacy_user_id`` is listed
# separately because we cannot repair it on an existing user.
_MUTABLE_CUSTOM_ATTRS = ("custom:org_id", "custom:role")
_IMMUTABLE_CUSTOM_ATTRS = ("custom:legacy_user_id",)


def _ddb_lookup_user(table: Any, email: str) -> dict[str, Any] | None:
    """Read the user record from the GSI4 (email) index."""
    response = table.query(
        IndexName="GSI4",
        KeyConditionExpression="GSI4PK = :pk",
        ExpressionAttributeValues={":pk": f"EMAIL#{email}"},
    )
    items = response.get("Items") or []
    return items[0] if items else None


def _cognito_get_sub(cognito: Any, user_pool_id: str, username: str) -> str | None:
    """Return the current Cognito ``sub`` attribute value, or None if missing."""
    response = cognito.admin_get_user(UserPoolId=user_pool_id, Username=username)
    for attribute in response.get("UserAttributes", []):
        if attribute["Name"] == "sub":
            return attribute["Value"]
    return None


def _stamp_mutable_custom_attrs(
    cognito: Any,
    user_pool_id: str,
    username: str,
    org_id: str,
    role: str,
    *,
    dry_run: bool,
) -> None:
    """Set ``custom:org_id`` + ``custom:role`` via admin-update-user-attributes."""
    attributes = [
        {"Name": "custom:org_id", "Value": org_id},
        {"Name": "custom:role", "Value": role},
    ]
    if dry_run:
        print(f"  [dry-run] would update {username}: {attributes}")
        return
    cognito.admin_update_user_attributes(
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=attributes,
    )
    print(f"  ✓ stamped {_MUTABLE_CUSTOM_ATTRS} on {username}")


def _backfill_ddb_cognito_sub(
    table: Any,
    user_id: str,
    new_sub: str,
    *,
    dry_run: bool,
) -> None:
    """Update the DDB user record's ``cognito_sub`` + ``GSI5PK`` to the new sub."""
    if dry_run:
        print(f"  [dry-run] would update DDB USER#{user_id} cognito_sub={new_sub}")
        return
    table.update_item(
        Key={"pk": f"USER#{user_id}", "sk": "USER#METADATA"},
        UpdateExpression="SET cognito_sub = :sub, GSI5PK = :gsi5pk",
        ExpressionAttributeValues={
            ":sub": new_sub,
            ":gsi5pk": f"COGNITO_SUB#{new_sub}",
        },
    )
    print(f"  ✓ backfilled DDB USER#{user_id} cognito_sub to {new_sub}")


def repair_user(
    *,
    cognito: Any,
    table: Any,
    user_pool_id: str,
    email: str,
    dry_run: bool,
) -> bool:
    """Repair a single user. Return True if all repair steps succeeded."""
    print(f"\n=== {email} ===")

    record = _ddb_lookup_user(table, email)
    if record is None:
        print(f"  ✗ no DDB record for {email} — skip")
        return False

    org_id = record.get("org_id")
    role = record.get("role", "analyst")
    user_id = record.get("id")
    persisted_sub = record.get("cognito_sub")
    if not org_id or not user_id:
        print(f"  ✗ DDB record missing org_id ({org_id!r}) or id ({user_id!r}) — skip")
        return False
    print(f"  DDB: org_id={org_id}  role={role}  id={user_id}  cognito_sub={persisted_sub!r}")

    new_sub = _cognito_get_sub(cognito, user_pool_id, email)
    if not new_sub:
        print(f"  ✗ Cognito user {email} has no `sub` — skip")
        return False
    print(f"  Cognito: new sub={new_sub}")

    _stamp_mutable_custom_attrs(
        cognito, user_pool_id, email, org_id, role, dry_run=dry_run
    )

    # Only rewrite DDB if the persisted sub differs from the new one. Avoids
    # a no-op write that would still register as an update for downstream
    # streams + consumers.
    if persisted_sub != new_sub:
        _backfill_ddb_cognito_sub(table, user_id, new_sub, dry_run=dry_run)
    else:
        print(f"  ✓ DDB cognito_sub already matches new Cognito sub — skip backfill")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--user-pool-id",
        required=True,
        help="Cognito user-pool ID, e.g. `us-east-1_JT4ly5noc`.",
    )
    parser.add_argument(
        "--table",
        required=True,
        help="DynamoDB table name, e.g. `sc0red-services-staging`.",
    )
    parser.add_argument(
        "--email",
        action="append",
        required=True,
        help="Email of a user to repair. Repeat for multiple users.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without mutating anything.",
    )
    arguments = parser.parse_args()

    region = os.environ.get("AWS_REGION", "us-east-1")
    session = boto3.session.Session(region_name=region)
    cognito = session.client("cognito-idp")
    table = session.resource("dynamodb").Table(arguments.table)

    successes = 0
    for email in arguments.email:
        if repair_user(
            cognito=cognito,
            table=table,
            user_pool_id=arguments.user_pool_id,
            email=email,
            dry_run=arguments.dry_run,
        ):
            successes += 1

    print(f"\nRepaired {successes}/{len(arguments.email)} users.")
    return 0 if successes == len(arguments.email) else 1


if __name__ == "__main__":
    sys.exit(main())
