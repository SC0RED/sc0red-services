#!/usr/bin/env python3
"""
E2E test data cleanup script.

Deletes test users from Cognito and ALL their data from DynamoDB:
- User record (USER#{id})
- Org record (ORG#{org_id})
- Invitations (ORG#{org_id} / INVITE#*)
- Companies (COMPANY#{id} via GSI1 lookup)
- Scans (SCAN#{id} + SCAN#{id}/COMPANY#* via GSI2 lookup)
- Assessments (ASSESSMENT#{id} + all sub-records via GSI3 lookup)

Test users are identified by the e2e-* email pattern in Cognito.

Usage:
    python3 scripts/e2e-cleanup.py \\
        --user-pool-id us-east-1_XXXXX \\
        --table janus-staging \\
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
        print(f"    Failed to delete Cognito user {username}: {error}", file=sys.stderr)
        return False


def query_gsi(dynamodb_client: object, table_name: str, index: str, pk_attr: str, pk_value: str) -> list[dict]:
    """Query a GSI and return all items."""
    items: list[dict] = []
    last_key = None

    while True:
        kwargs: dict[str, object] = {
            "TableName": table_name,
            "IndexName": index,
            "KeyConditionExpression": f"{pk_attr} = :pk",
            "ExpressionAttributeValues": {":pk": {"S": pk_value}},
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key

        response = dynamodb_client.query(**kwargs)
        items.extend(response.get("Items", []))

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

    return items


def query_pk(dynamodb_client: object, table_name: str, pk_value: str) -> list[dict]:
    """Query the main table by pk and return all items (all sk values)."""
    items: list[dict] = []
    last_key = None

    while True:
        kwargs: dict[str, object] = {
            "TableName": table_name,
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": {"S": pk_value}},
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key

        response = dynamodb_client.query(**kwargs)
        items.extend(response.get("Items", []))

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

    return items


def delete_items(dynamodb_client: object, table_name: str, items: list[dict]) -> int:
    """Delete a list of DynamoDB items by their pk/sk."""
    deleted = 0
    for item in items:
        pk = item["pk"]["S"]
        sk = item["sk"]["S"]
        try:
            dynamodb_client.delete_item(
                TableName=table_name,
                Key={"pk": {"S": pk}, "sk": {"S": sk}},
            )
            deleted += 1
        except ClientError as error:
            print(f"    Failed to delete {pk}/{sk}: {error}", file=sys.stderr)
    return deleted


def cleanup_org_data(dynamodb_client: object, table_name: str, org_id: str, user_id: str, dry_run: bool) -> int:
    """Delete all DynamoDB records for an org: user, org, invites, companies, scans, assessments."""
    total = 0

    # 1. User record: USER#{user_id}
    user_items = query_pk(dynamodb_client, table_name, f"USER#{user_id}")
    if dry_run:
        print(f"    Would delete {len(user_items)} USER record(s)")
    else:
        total += delete_items(dynamodb_client, table_name, user_items)

    # 2. Org record + invites: ORG#{org_id} (includes ORG#METADATA + INVITE#*)
    org_items = query_pk(dynamodb_client, table_name, f"ORG#{org_id}")
    if dry_run:
        print(f"    Would delete {len(org_items)} ORG record(s) (metadata + invites)")
    else:
        total += delete_items(dynamodb_client, table_name, org_items)

    # 3. Companies: GSI1 pk=ORG#{org_id} → get company IDs → delete COMPANY#{id} records
    company_gsi_items = query_gsi(dynamodb_client, table_name, "GSI1", "GSI1PK", f"ORG#{org_id}")
    company_ids = set()
    for item in company_gsi_items:
        pk = item["pk"]["S"]
        if pk.startswith("COMPANY#"):
            company_ids.add(pk.replace("COMPANY#", ""))

    for company_id in company_ids:
        company_items = query_pk(dynamodb_client, table_name, f"COMPANY#{company_id}")
        if dry_run:
            print(f"    Would delete {len(company_items)} record(s) for COMPANY#{company_id}")
        else:
            total += delete_items(dynamodb_client, table_name, company_items)

        # 4. Assessments for this company: GSI3 pk=COMPANY#{company_id}
        assessment_gsi_items = query_gsi(dynamodb_client, table_name, "GSI3", "GSI3PK", f"COMPANY#{company_id}")
        assessment_ids = set()
        for item in assessment_gsi_items:
            pk = item["pk"]["S"]
            if pk.startswith("ASSESSMENT#"):
                assessment_ids.add(pk.replace("ASSESSMENT#", ""))

        for assessment_id in assessment_ids:
            assessment_items = query_pk(dynamodb_client, table_name, f"ASSESSMENT#{assessment_id}")
            if dry_run:
                print(f"    Would delete {len(assessment_items)} record(s) for ASSESSMENT#{assessment_id}")
            else:
                total += delete_items(dynamodb_client, table_name, assessment_items)

    # 5. Scans: GSI2 pk=ORG#{org_id} → get scan IDs → delete SCAN#{id} records
    scan_gsi_items = query_gsi(dynamodb_client, table_name, "GSI2", "GSI2PK", f"ORG#{org_id}")
    scan_ids = set()
    for item in scan_gsi_items:
        pk = item["pk"]["S"]
        if pk.startswith("SCAN#"):
            scan_ids.add(pk.replace("SCAN#", ""))

    for scan_id in scan_ids:
        scan_items = query_pk(dynamodb_client, table_name, f"SCAN#{scan_id}")
        if dry_run:
            print(f"    Would delete {len(scan_items)} record(s) for SCAN#{scan_id}")
        else:
            total += delete_items(dynamodb_client, table_name, scan_items)

    return total


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
        user_id = user["sub"]
        print(f"\n  User: {user['email']} (org_id: {org_id})")

        if not org_id:
            print("    No org_id found — skipping DynamoDB cleanup")
        else:
            total = cleanup_org_data(dynamodb, args.table, org_id, user_id, args.dry_run)
            if not args.dry_run:
                print(f"    Deleted {total} DynamoDB record(s)")

        if args.dry_run:
            print("    [DRY RUN] Would delete Cognito user")
        elif delete_cognito_user(cognito, args.user_pool_id, user["username"]):
            print(f"    Deleted Cognito user")

    print(f"\nCleanup complete. Processed {len(users)} user(s).")


if __name__ == "__main__":
    main()
