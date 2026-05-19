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
        --table sc0red-services-staging \\
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


def find_orphaned_dynamodb_users(dynamodb_client: object, table_name: str) -> list[dict[str, str]]:
    """Find USER# records in DynamoDB with e2e-* email (orphaned after Cognito deletion)."""
    users: list[dict[str, str]] = []
    last_key = None

    while True:
        kwargs: dict[str, object] = {
            "TableName": table_name,
            "FilterExpression": "begins_with(pk, :prefix) AND contains(email, :e2e)",
            "ExpressionAttributeValues": {
                ":prefix": {"S": "USER#"},
                ":e2e": {"S": "e2e-"},
            },
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key

        response = dynamodb_client.scan(**kwargs)

        for item in response.get("Items", []):
            users.append({
                "id": item["pk"]["S"].replace("USER#", ""),
                "email": item.get("email", {}).get("S", ""),
                "org_id": item.get("org_id", {}).get("S", ""),
            })

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break

    return users


def discover_user_pool_id(cognito_client: object) -> str:
    """Find the sc0red Services Cognito user pool by name pattern (sc0red-services-users-*)."""
    response = cognito_client.list_user_pools(MaxResults=60)
    for pool in response.get("UserPools", []):
        if pool["Name"].startswith("sc0red-services-users-"):
            print(f"  Auto-discovered user pool: {pool['Name']} ({pool['Id']})")
            return pool["Id"]
    return ""


def discover_table_name(dynamodb_client: object) -> str:
    """Find the sc0red Services DynamoDB table by name pattern (sc0red-services-*)."""
    response = dynamodb_client.list_tables()
    for name in response.get("TableNames", []):
        if name.startswith("sc0red-services-") and name != "sc0red-services-e2e":
            print(f"  Auto-discovered table: {name}")
            return name
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up E2E test data")
    parser.add_argument("--user-pool-id", default="", help="Cognito User Pool ID (auto-discovered if omitted)")
    parser.add_argument("--table", default="", help="DynamoDB table name (auto-discovered if omitted)")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--dry-run", action="store_true", help="List what would be deleted without deleting")
    args = parser.parse_args()

    cognito = boto3.client("cognito-idp", region_name=args.region)
    dynamodb = boto3.client("dynamodb", region_name=args.region)

    # Auto-discover resources if not provided
    user_pool_id = args.user_pool_id
    table_name = args.table

    if not user_pool_id:
        print("Auto-discovering Cognito user pool...")
        user_pool_id = discover_user_pool_id(cognito)
        if not user_pool_id:
            print("ERROR: No sc0red-services-users-* user pool found. Pass --user-pool-id explicitly.", file=sys.stderr)
            sys.exit(1)

    if not table_name:
        print("Auto-discovering DynamoDB table...")
        table_name = discover_table_name(dynamodb)
        if not table_name:
            print("ERROR: No sc0red-services-* table found. Pass --table explicitly.", file=sys.stderr)
            sys.exit(1)

    # 1. Find E2E test users in Cognito
    print(f"\nScanning Cognito pool {user_pool_id} for e2e-* users...")
    cognito_users = find_e2e_cognito_users(cognito, user_pool_id)
    print(f"  Found {len(cognito_users)} Cognito user(s)")

    # 2. Find orphaned E2E user records in DynamoDB (Cognito user already deleted)
    print(f"\nScanning DynamoDB {table_name} for orphaned e2e-* user records...")
    orphaned_users = find_orphaned_dynamodb_users(dynamodb, table_name)
    cognito_user_ids = {u["sub"] for u in cognito_users}
    orphaned_users = [u for u in orphaned_users if u["id"] not in cognito_user_ids]
    print(f"  Found {len(orphaned_users)} orphaned DynamoDB user(s)")

    if not cognito_users and not orphaned_users:
        print("Nothing to clean up.")
        return

    # 3. Clean up Cognito users + their DynamoDB data
    for user in cognito_users:
        org_id = user["org_id"]
        uid = user["sub"]
        print(f"\n  Cognito user: {user['email']} (org_id: {org_id})")

        if org_id:
            total = cleanup_org_data(dynamodb, table_name, org_id, uid, args.dry_run)
            if not args.dry_run:
                print(f"    Deleted {total} DynamoDB record(s)")
        else:
            print("    No org_id found — skipping DynamoDB cleanup")

        if args.dry_run:
            print("    [DRY RUN] Would delete Cognito user")
        elif delete_cognito_user(cognito, user_pool_id, user["username"]):
            print(f"    Deleted Cognito user")

    # 4. Clean up orphaned DynamoDB records (Cognito user was already deleted)
    for user in orphaned_users:
        org_id = user["org_id"]
        uid = user["id"]
        print(f"\n  Orphaned DynamoDB user: {user['email']} (org_id: {org_id})")

        if org_id:
            total = cleanup_org_data(dynamodb, table_name, org_id, uid, args.dry_run)
            if not args.dry_run:
                print(f"    Deleted {total} DynamoDB record(s)")
        else:
            # At minimum delete the USER# record itself
            user_items = query_pk(dynamodb, table_name, f"USER#{uid}")
            if args.dry_run:
                print(f"    [DRY RUN] Would delete {len(user_items)} USER record(s)")
            else:
                total = delete_items(dynamodb, table_name, user_items)
                print(f"    Deleted {total} DynamoDB record(s)")

    processed = len(cognito_users) + len(orphaned_users)
    print(f"\nCleanup complete. Processed {processed} user(s).")


if __name__ == "__main__":
    main()
