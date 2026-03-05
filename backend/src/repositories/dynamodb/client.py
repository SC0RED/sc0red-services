"""DynamoDB table wrapper for single-table design.

Provides low-level operations (put, get, query, delete) over the Janus
single-table DynamoDB design.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)


def _convert_floats(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats(v) for v in obj]
    return obj


class DynamoDBTable:
    """Wrapper around a single DynamoDB table."""

    def __init__(self, table_name: str | None = None, endpoint_url: str | None = None) -> None:
        self._table_name = table_name or os.environ.get("DYNAMODB_TABLE", "janus-dev")
        self._endpoint_url = endpoint_url or os.environ.get("DYNAMODB_ENDPOINT")

        kwargs: dict[str, Any] = {}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
            kwargs["region_name"] = os.environ.get("AWS_REGION", "us-east-1")

        dynamodb = boto3.resource("dynamodb", **kwargs)
        self._table = dynamodb.Table(self._table_name)

    @property
    def table_name(self) -> str:
        return self._table_name

    def put_item(self, item: dict[str, Any]) -> None:
        self._table.put_item(Item=_convert_floats(item))

    def get_item(self, pk: str, sk: str) -> dict[str, Any] | None:
        response = self._table.get_item(Key={"pk": pk, "sk": sk})
        return response.get("Item")

    def delete_item(self, pk: str, sk: str) -> None:
        self._table.delete_item(Key={"pk": pk, "sk": sk})

    def query(
        self,
        pk: str,
        sk_prefix: str | None = None,
        index_name: str | None = None,
        limit: int | None = None,
        scan_forward: bool = True,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {}
        if index_name:
            kwargs["IndexName"] = index_name

        key_condition = Key("pk").eq(pk)
        if sk_prefix:
            key_condition = key_condition & Key("sk").begins_with(sk_prefix)

        kwargs["KeyConditionExpression"] = key_condition
        kwargs["ScanIndexForward"] = scan_forward

        if limit:
            kwargs["Limit"] = limit

        response = self._table.query(**kwargs)
        return response.get("Items", [])

    def query_gsi(
        self,
        index_name: str,
        pk_attr: str,
        pk_value: str,
        sk_attr: str | None = None,
        sk_prefix: str | None = None,
    ) -> list[dict[str, Any]]:
        key_condition = Key(pk_attr).eq(pk_value)
        if sk_attr and sk_prefix:
            key_condition = key_condition & Key(sk_attr).begins_with(sk_prefix)

        response = self._table.query(
            IndexName=index_name,
            KeyConditionExpression=key_condition,
        )
        return response.get("Items", [])

    def update_item(
        self,
        pk: str,
        sk: str,
        updates: dict[str, Any],
    ) -> None:
        if not updates:
            return

        expressions = []
        names: dict[str, str] = {}
        values: dict[str, Any] = {}

        for i, (key, value) in enumerate(updates.items()):
            attr_name = f"#attr{i}"
            attr_value = f":val{i}"
            expressions.append(f"{attr_name} = {attr_value}")
            names[attr_name] = key
            values[attr_value] = _convert_floats(value)

        self._table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression="SET " + ", ".join(expressions),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def batch_delete(self, keys: list[dict[str, str]]) -> None:
        with self._table.batch_writer() as batch:
            for key in keys:
                batch.delete_item(Key=key)
