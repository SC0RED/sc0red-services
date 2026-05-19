#!/usr/bin/env python3
"""Idempotent DynamoDB table setup for local dev and E2E tests."""

import argparse

import boto3

GSI_COUNT = 5


def setup_table(table_name: str, endpoint: str) -> None:
    """Create the sc0red Services DynamoDB table with GSIs if it does not exist."""
    ddb = boto3.client(
        "dynamodb",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="local",
        aws_secret_access_key="local",
    )
    attribute_definitions = [
        {"AttributeName": "pk", "AttributeType": "S"},
        {"AttributeName": "sk", "AttributeType": "S"},
    ]
    gsi_definitions = []
    for i in range(1, GSI_COUNT + 1):
        pk_name = f"GSI{i}PK"
        sk_name = f"GSI{i}SK"
        attribute_definitions.extend([
            {"AttributeName": pk_name, "AttributeType": "S"},
            {"AttributeName": sk_name, "AttributeType": "S"},
        ])
        gsi_definitions.append({
            "IndexName": f"GSI{i}",
            "KeySchema": [
                {"AttributeName": pk_name, "KeyType": "HASH"},
                {"AttributeName": sk_name, "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        })
    try:
        ddb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=attribute_definitions,
            GlobalSecondaryIndexes=gsi_definitions,
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Table '{table_name}' created")
    except ddb.exceptions.ResourceInUseException:
        print(f"Table '{table_name}' already exists")

    # Soft-delete recovery: tombstoned rows carry a `ttl` epoch-seconds
    # attribute set to deleted_at + 90 days. DynamoDB TTL evicts them
    # automatically. Mirrors the prod CDK config in
    # infrastructure/stacks/stack_resources.py:create_table — local dev
    # MUST match production infrastructure (see CLAUDE.md
    # "Local Dev = Production Parity").
    try:
        ddb.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
        )
        print(f"TTL enabled on '{table_name}' (attribute=ttl)")
    except ddb.exceptions.ClientError as error:
        # LocalStack returns ValidationException when TTL is already
        # enabled with the same attribute; treat as idempotent.
        message = str(error)
        if "TimeToLive is already enabled" in message or "already enabled" in message:
            print(f"TTL already enabled on '{table_name}'")
        else:
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup DynamoDB table")
    parser.add_argument("--table", default="sc0red-services-dev")
    parser.add_argument("--endpoint", default="http://localhost:8000")
    args = parser.parse_args()
    setup_table(args.table, args.endpoint)
