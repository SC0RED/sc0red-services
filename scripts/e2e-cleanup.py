#!/usr/bin/env python3
"""
E2E test data cleanup script.

Deletes test users from Cognito and their data from DynamoDB.
Test users are identified by the e2e-* email pattern.

Usage:
    python3 scripts/e2e-cleanup.py \
        --user-pool-id us-east-1_XXXXX \
        --table janus-staging \
        --region us-east-1

Environment variables:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
"""

import argparse
import sys

import boto3
from botocore.exceptions import ClientError


def find_e2e_cognito_users(cognito_client: object, user_pool_id: str) -> list[dict[str, str]]:
    """Find all Cognito users with e2e-* email pattern."""
    users: list[dict[str, str]] = []
    pagination_token = None

    while True:
        kwargs: dict[str, object] = {
            "UserPoolId": user_pool_id,
            "Filter": 'email ^= "e2e-"',
            "Limit": 60,
        }
        if pagination_token:
            kwargs["PaginationToken"] = pagination_token

        response = cognito_client.list_users(**kwargs)

        for user in response.get("Users", []):
            email = ""
            sub = ""
            org_id = ""
            for attr in user.get("Attributes", []):
                if attr["Name"] == "email":
                    email = attr["Value"]
                elif attr["Name"] == "sub":
                    sub = attr["Value"]
                elif attr["Name"] == "custom:org_id":
                    org_id = attr["Value"]
            if email:
                users.append({
                    "username": user["Username"],
                    "email": email,
                    "sub": sub,
                    "org_id": org_id,
                })

        pagination_token = response.get("PaginationToken")
        if not pagination_token:
            break

    return users


def delete_cognito_user(cognito_client: object, user_pool_id: str, username: str) -> bool:
    """Delete a single Cognito user."""
    try:
        cognito_client.admin_delete_user(UserPoolId=user_pool_id, Username=username)
        return True
    except ClientError as error:
        print(f"  Failed to delete Cognito user {username}: {error}", file=sys.stderr)
        return False


def delete_dynamodb_records_by_pk_prefix(dynamodb_client: object, table_name: str, prefix: str) -> int:
    """Delete all DynamoDB records where pk starts with the given prefix."""
    deleted = 0
    last_key = None

    while True:
        kwargs: dict[str, object] = {
            "TableName": table_name,
            "FilterExpression": "begins_with(pk, :prefix)",
            "ExpressionAttributeValues": {":prefix": {"S": prefix}},
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key

        response = dynamodb_client.scan(**kwargs)

        for item in response.get("Items", []):
            pk = item["pk"]["S"]
            sk = item["sk"]["S"]
            try:
                dynamodb_client.delete_item(
                    TableName=table_name,
                    Key={"pk": {"S": pk}, "sk": {"S": sk}},
                )
                deleted += 1
            except ClientError as error:
                print(f"  Failed to delete {pk}/{sk}: {error}", file=sys.stderr)

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up E2E test data")
    parser.add_argument("--user-pool-id", required=True, help="Cognito User Pool ID")
    parser.add_argument("--table", required=True, help="DynamoDB table name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--dry-run", action="store_true", help="List what would be deleted without deleting")
    args = parser.parse_args()

    cognito = boto3.client("cognito-idp", region_name=args.region)
    dynamodb = boto3.client("dynamodb", region_name=args.region)

    # 1. Find E2E test users in Cognito
    print(f"Scanning Cognito pool {args.user_pool_id} for e2e-* users...")
    users = find_e2e_cognito_users(cognito, args.user_pool_id)
    print(f"  Found {len(users)} E2E test user(s)")

    if not users:
        print("Nothing to clean up.")
        return

    for user in users:
        org_id = user["org_id"]
        print(f"\n  User: {user['email']} (org_id: {org_id})")

        if args.dry_run:
            print("    [DRY RUN] Would delete Cognito user and DynamoDB records")
            continue

        # 2. Delete org data from DynamoDB (ORG#{org_id} prefix covers all org records:
        #    org metadata, users, invitations, scans, analyses)
        if org_id:
            org_records = delete_dynamodb_records_by_pk_prefix(dynamodb, args.table, f"ORG#{org_id}")
            print(f"    Deleted {org_records} DynamoDB record(s) for ORG#{org_id}")
        else:
            print("    No org_id found — skipping DynamoDB cleanup")

        # 3. Delete Cognito user
        if delete_cognito_user(cognito, args.user_pool_id, user["username"]):
            print(f"    Deleted Cognito user {user['email']}")

    print(f"\nCleanup complete. Processed {len(users)} user(s).")


if __name__ == "__main__":
    main()
