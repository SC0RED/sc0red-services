#!/usr/bin/env python3
"""One-time script: migrate all DynamoDB users to Cognito.

For each user in DynamoDB who doesn't already exist in Cognito,
creates a Cognito user with their custom attributes (org_id, role,
legacy_user_id) and FORCE_CHANGE_PASSWORD status.

Users will be prompted to reset their password on next login.

Usage:
    # Dry run (default) — shows what would happen
    python scripts/migrate_users_to_cognito.py

    # Actually migrate
    python scripts/migrate_users_to_cognito.py --execute

    # With custom table/pool
    python scripts/migrate_users_to_cognito.py --execute \
        --table janus-staging \
        --pool-id us-east-1_XXXXXXXXX

Environment:
    AWS credentials must be configured (via env vars, profile, or IAM role).
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3
from botocore.exceptions import ClientError


def get_all_dynamodb_users(table_name: str, region: str) -> list[dict]:
    """Scan DynamoDB for all user records."""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    users = []
    scan_kwargs = {
        "FilterExpression": "entity_type = :et",
        "ExpressionAttributeValues": {":et": "user"},
    }

    while True:
        response = table.scan(**scan_kwargs)
        users.extend(response.get("Items", []))

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return users


def check_cognito_user_exists(cognito_client: object, pool_id: str, email: str) -> bool:
    """Check if a user already exists in Cognito."""
    try:
        cognito_client.admin_get_user(
            UserPoolId=pool_id,
            Username=email,
        )
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] == "UserNotFoundException":
            return False
        raise


def create_cognito_user(
    cognito_client: object,
    pool_id: str,
    user: dict,
) -> str:
    """Create a Cognito user from a DynamoDB user record.

    Returns 'created', 'exists', or 'error: <message>'.
    """
    email = user.get("email", "")
    if not email:
        return "error: no email"

    if check_cognito_user_exists(cognito_client, pool_id, email):
        return "exists"

    try:
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": user.get("name", "")},
                {"Name": "custom:org_id", "Value": user.get("org_id", "")},
                {"Name": "custom:role", "Value": user.get("role", "analyst")},
                {"Name": "custom:legacy_user_id", "Value": user.get("id", "")},
            ],
            MessageAction="SUPPRESS",
        )
        return "created"
    except ClientError as error:
        return f"error: {error.response['Error']['Code']}"


def main() -> None:
    """Run the migration."""
    parser = argparse.ArgumentParser(description="Migrate DynamoDB users to Cognito")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually create users in Cognito (default is dry run)",
    )
    parser.add_argument(
        "--table",
        default=os.environ.get("DYNAMODB_TABLE", "janus-staging"),
        help="DynamoDB table name",
    )
    parser.add_argument(
        "--pool-id",
        default=os.environ.get("COGNITO_USER_POOL_ID", ""),
        help="Cognito User Pool ID",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1)",
    )
    arguments = parser.parse_args()

    if not arguments.pool_id:
        print("Error: --pool-id or COGNITO_USER_POOL_ID required")
        sys.exit(1)

    region = arguments.region

    print(f"Table:   {arguments.table}")
    print(f"Pool ID: {arguments.pool_id}")
    print(f"Region:  {region}")
    print(f"Mode:    {'EXECUTE' if arguments.execute else 'DRY RUN'}")
    print()

    users = get_all_dynamodb_users(arguments.table, region)
    print(f"Found {len(users)} users in DynamoDB")
    print()

    if not users:
        print("Nothing to migrate.")
        return

    cognito_client = boto3.client("cognito-idp", region_name=region)

    created = 0
    exists = 0
    errors = 0

    for user in users:
        email = user.get("email", "(no email)")
        user_id = user.get("id", "(no id)")
        org_id = user.get("org_id", "(no org)")
        role = user.get("role", "analyst")

        if arguments.execute:
            result = create_cognito_user(cognito_client, arguments.pool_id, user)
        else:
            # Dry run — just check existence
            if check_cognito_user_exists(cognito_client, arguments.pool_id, email):
                result = "exists"
            else:
                result = "would create"

        status_icon = {"created": "+", "exists": "=", "would create": "?"}
        icon = status_icon.get(result, "!")

        print(f"  [{icon}] {email:<40} org={org_id[:12]}.. role={role:<8} → {result}")

        if result == "created" or result == "would create":
            created += 1
        elif result == "exists":
            exists += 1
        else:
            errors += 1

    print()
    print(f"Summary: {created} {'created' if arguments.execute else 'to create'}, "
          f"{exists} already in Cognito, {errors} errors")

    if not arguments.execute and created > 0:
        print()
        print(f"Run with --execute to migrate {created} user(s)")


if __name__ == "__main__":
    main()
