#!/usr/bin/env python3
"""Idempotent DynamoDB table setup for local dev and E2E tests."""

import argparse

import boto3

GSI_COUNT = 4


def setup_table(table_name: str, endpoint: str) -> None:
    """Create the Janus DynamoDB table with GSIs if it does not exist."""
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup DynamoDB table")
    parser.add_argument("--table", default="janus-dev")
    parser.add_argument("--endpoint", default="http://localhost:8000")
    args = parser.parse_args()
    setup_table(args.table, args.endpoint)
