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


def _convert_floats(value: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _convert_floats(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_floats(v) for v in value]
    return value


class DynamoDBTable:
    """Wrapper around a single DynamoDB table."""

    def __init__(self, table_name: str | None = None, endpoint_url: str | None = None) -> None:
        self._table_name = table_name or os.environ.get("DYNAMODB_TABLE", "janus-dev")
        self._endpoint_url = endpoint_url or os.environ.get("DYNAMODB_ENDPOINT")

        kwargs: dict[str, Any] = {}
        if self._endpoint_url:
            kwargs["endpoint_url"] = self._endpoint_url
            kwargs["region_name"] = os.environ.get("AWS_REGION", "us-east-1")

        self._dynamodb = boto3.resource("dynamodb", **kwargs)
        self._table = self._dynamodb.Table(self._table_name)

    @property
    def table_name(self) -> str:
        """Return the DynamoDB table name."""
        return self._table_name

    def put_item(self, item: dict[str, Any]) -> None:
        """Write a single item to the table, converting floats to Decimal."""
        self._table.put_item(Item=_convert_floats(item))

    def get_item(self, pk: str, sk: str) -> dict[str, Any] | None:
        """Retrieve a single item by primary key, or None if not found."""
        response = self._table.get_item(Key={"pk": pk, "sk": sk})
        return response.get("Item")

    def delete_item(self, pk: str, sk: str) -> None:
        """Delete a single item by primary key."""
        self._table.delete_item(Key={"pk": pk, "sk": sk})

    def query(
        self,
        pk: str,
        sk_prefix: str | None = None,
        index_name: str | None = None,
        limit: int | None = None,
        scan_forward: bool = True,
        consistent_read: bool = False,
    ) -> list[dict[str, Any]]:
        """Query items by partition key, with optional sort-key prefix.

        Automatically paginates through all results using LastEvaluatedKey.
        If limit is specified, returns at most that many items.

        Pass ``consistent_read=True`` for read-after-write consistency on
        the base table — the default eventually-consistent read can lag by
        up to ~100ms, which is fine for most reads but breaks workflows
        that depend on observing prior writes in the same handler run
        (e.g., the bulk-delete cascade-pass in
        ``analysis_handlers.handle_bulk_delete_analyses`` after
        ``unlink_company`` writes). GSI queries (``index_name`` set) cannot
        use consistent reads — DynamoDB rejects the combination — so this
        flag is silently ignored when an index is targeted.
        """
        kwargs: dict[str, Any] = {}
        if index_name:
            kwargs["IndexName"] = index_name
        elif consistent_read:
            # GSI reads are eventually consistent by DynamoDB design;
            # ConsistentRead only applies to base-table queries.
            kwargs["ConsistentRead"] = True

        key_condition = Key("pk").eq(pk)
        if sk_prefix:
            key_condition = key_condition & Key("sk").begins_with(sk_prefix)

        kwargs["KeyConditionExpression"] = key_condition
        kwargs["ScanIndexForward"] = scan_forward

        items: list[dict[str, Any]] = []
        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items", []))

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            if limit and len(items) >= limit:
                break
            kwargs["ExclusiveStartKey"] = last_key

        return items[:limit] if limit else items

    def query_gsi(
        self,
        index_name: str,
        pk_attr: str,
        pk_value: str,
        sk_attr: str | None = None,
        sk_prefix: str | None = None,
        limit: int | None = None,
        cursor: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Query a GSI with optional pagination.

        Returns (items, last_evaluated_key). If last_evaluated_key is None,
        there are no more results. Pass it as cursor to fetch the next page.
        """
        key_condition = Key(pk_attr).eq(pk_value)
        if sk_attr and sk_prefix:
            key_condition = key_condition & Key(sk_attr).begins_with(sk_prefix)

        kwargs: dict[str, Any] = {
            "IndexName": index_name,
            "KeyConditionExpression": key_condition,
        }
        if cursor:
            kwargs["ExclusiveStartKey"] = cursor
        if limit:
            kwargs["Limit"] = limit

        items: list[dict[str, Any]] = []
        last_key: dict[str, Any] | None = None

        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items", []))

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            if limit and len(items) >= limit:
                break
            kwargs["ExclusiveStartKey"] = last_key

        if limit:
            return items[:limit], last_key
        return items, None

    def batch_get(self, keys: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Fetch multiple items via BatchGetItem, retrying any unprocessed keys.

        DynamoDB may not process all keys in one shot due to throughput
        limits. Unprocessed keys are returned in the response and must be
        retried — otherwise items are silently dropped.
        """
        if not keys:
            return []

        request_keys = [{"pk": k["pk"], "sk": k["sk"]} for k in keys]
        results: list[dict[str, Any]] = []

        while request_keys:
            response = self._dynamodb.batch_get_item(
                RequestItems={self._table_name: {"Keys": request_keys}}
            )
            results.extend(response.get("Responses", {}).get(self._table_name, []))

            # Retry any keys that DynamoDB didn't process in this batch
            unprocessed = response.get("UnprocessedKeys", {})
            request_keys = unprocessed.get(self._table_name, {}).get("Keys", [])

        return results

    def update_item(
        self,
        pk: str,
        sk: str,
        updates: dict[str, Any],
    ) -> None:
        """Update specific attributes on an existing item using a SET expression."""
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

    def remove_attributes(
        self,
        pk: str,
        sk: str,
        attribute_names: list[str],
        *,
        require_exists: bool = False,
    ) -> None:
        """Remove the given attributes from an item via a REMOVE expression.

        Used by the soft-delete recovery path — tombstoned records carry
        `deleted_at` + `ttl` attributes; restoring a record means
        REMOVING (not just nulling) those attributes so the item is
        indistinguishable from one that was never deleted. SET-to-None
        wouldn't work: DynamoDB still considers the attribute present,
        and the read filter (`if not item.get('deleted_at')`) would
        also miss it (None is falsy), but `ttl` set to None breaks the
        TTL service which expects either absent-or-numeric.

        Pass ``require_exists=True`` to gate the update on the row
        already existing — DynamoDB ``UpdateItem`` with no
        ``ConditionExpression`` happily creates a `{pk, sk}` shell when
        the row is gone, which is *exactly* what happens when TTL
        evicts a tombstoned record between the recovery flow's read
        and write. Restore callers MUST set this flag so that an
        eviction race surfaces as a ``ClientError`` (code
        ``ConditionalCheckFailedException``) instead of a silent
        empty-shell write that looks restored but has lost all data.
        """
        if not attribute_names:
            return

        expressions: list[str] = []
        names: dict[str, str] = {}
        for index, name in enumerate(attribute_names):
            attr_name = f"#attr{index}"
            expressions.append(attr_name)
            names[attr_name] = name

        kwargs: dict[str, Any] = {
            "Key": {"pk": pk, "sk": sk},
            "UpdateExpression": "REMOVE " + ", ".join(expressions),
            "ExpressionAttributeNames": names,
        }
        if require_exists:
            kwargs["ConditionExpression"] = "attribute_exists(pk)"

        self._table.update_item(**kwargs)

    def batch_write(self, items: list[dict[str, Any]]) -> None:
        """Write multiple items using a batch writer (max 25 per request, auto-batched)."""
        with self._table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=_convert_floats(item))

    def batch_delete(self, keys: list[dict[str, str]]) -> None:
        """Delete multiple items by their primary keys using a batch writer."""
        with self._table.batch_writer() as batch:
            for key in keys:
                batch.delete_item(Key=key)
