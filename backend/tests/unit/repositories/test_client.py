"""Tests for DynamoDB client utilities."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from moto import mock_aws

from src.repositories.dynamodb.client import DynamoDBTable, _convert_floats


class TestConvertFloats:
    def test_float_to_decimal(self):
        result = _convert_floats(3.14)
        assert isinstance(result, Decimal)
        assert result == Decimal("3.14")

    def test_dict_with_floats(self):
        result = _convert_floats({"score": 7.5, "name": "test"})
        assert isinstance(result["score"], Decimal)
        assert result["score"] == Decimal("7.5")
        assert result["name"] == "test"

    def test_nested_dict(self):
        result = _convert_floats({"outer": {"inner": 1.5}})
        assert isinstance(result["outer"]["inner"], Decimal)

    def test_list_with_floats(self):
        result = _convert_floats([1.1, 2.2, "text"])
        assert isinstance(result[0], Decimal)
        assert isinstance(result[1], Decimal)
        assert result[2] == "text"

    def test_int_unchanged(self):
        result = _convert_floats(42)
        assert result == 42
        assert isinstance(result, int)

    def test_string_unchanged(self):
        result = _convert_floats("hello")
        assert result == "hello"

    def test_none_unchanged(self):
        result = _convert_floats(None)
        assert result is None

    def test_bool_unchanged(self):
        result = _convert_floats(True)
        assert result is True

    def test_complex_nested_structure(self):
        data = {
            "pk": "TEST#1",
            "score": 5.5,
            "items": [{"value": 3.2}, {"value": 7.8}],
            "metadata": {"nested": {"deep": 1.1}},
        }
        result = _convert_floats(data)
        assert result["pk"] == "TEST#1"
        assert isinstance(result["score"], Decimal)
        assert isinstance(result["items"][0]["value"], Decimal)
        assert isinstance(result["metadata"]["nested"]["deep"], Decimal)


class TestDynamoDBTable:
    @mock_aws
    def test_init_with_explicit_endpoint_url(self, dynamodb_table):
        """DynamoDBTable init with explicit endpoint_url sets kwargs correctly."""
        # The conftest fixture already creates a table with endpoint_url=None.
        # We test that providing an endpoint_url creates a table without error.
        with patch("src.repositories.dynamodb.client.boto3") as mock_boto3:
            mock_resource = MagicMock()
            mock_boto3.resource.return_value = mock_resource
            mock_resource.Table.return_value = MagicMock()

            DynamoDBTable(table_name="janus-test", endpoint_url="http://localhost:8000")

            mock_boto3.resource.assert_called_once()
            call_kwargs = mock_boto3.resource.call_args
            assert call_kwargs[1]["endpoint_url"] == "http://localhost:8000"

    @mock_aws
    def test_table_name_property(self, dynamodb_table):
        """table_name property returns the configured table name."""
        assert dynamodb_table.table_name == "janus-test"

    def test_query_with_index_name(self):
        """query() passes IndexName when index_name is provided."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": [{"pk": "X", "sk": "Y"}]}

        with patch("src.repositories.dynamodb.client.boto3") as mock_boto3:
            mock_boto3.resource.return_value.Table.return_value = mock_table
            table = DynamoDBTable(table_name="test-table")

        results = table.query(pk="IDX#A", index_name="GSI1")
        assert len(results) == 1

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["IndexName"] == "GSI1"

    def test_query_default_does_not_request_consistent_read(self):
        """Default query is eventually consistent — `ConsistentRead` is absent."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        with patch("src.repositories.dynamodb.client.boto3") as mock_boto3:
            mock_boto3.resource.return_value.Table.return_value = mock_table
            table = DynamoDBTable(table_name="test-table")

        table.query(pk="X")

        call_kwargs = mock_table.query.call_args[1]
        assert "ConsistentRead" not in call_kwargs

    def test_query_with_consistent_read_passes_kwarg(self):
        """`consistent_read=True` propagates to ``ConsistentRead=True`` for base-table reads.

        Required for the bulk-delete cascade pass — the cascade decision
        must observe in-loop unlinks within the same handler run.
        """
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        with patch("src.repositories.dynamodb.client.boto3") as mock_boto3:
            mock_boto3.resource.return_value.Table.return_value = mock_table
            table = DynamoDBTable(table_name="test-table")

        table.query(pk="SCAN#x", sk_prefix="COMPANY#", consistent_read=True)

        call_kwargs = mock_table.query.call_args[1]
        assert call_kwargs["ConsistentRead"] is True

    def test_query_consistent_read_silently_dropped_for_gsi(self):
        """DynamoDB GSI reads are inherently eventually consistent — passing
        `consistent_read=True` alongside `index_name` must NOT send
        ``ConsistentRead=True`` to boto3 (it would 400)."""
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}

        with patch("src.repositories.dynamodb.client.boto3") as mock_boto3:
            mock_boto3.resource.return_value.Table.return_value = mock_table
            table = DynamoDBTable(table_name="test-table")

        table.query(pk="ORG#x", index_name="GSI1", consistent_read=True)

        call_kwargs = mock_table.query.call_args[1]
        assert "ConsistentRead" not in call_kwargs
        assert call_kwargs["IndexName"] == "GSI1"

    @mock_aws
    def test_query_with_limit(self, dynamodb_table):
        """query() respects limit parameter."""
        for i in range(5):
            dynamodb_table.put_item(
                {
                    "pk": "BATCH#1",
                    "sk": f"ITEM#{i:04d}",
                }
            )

        results = dynamodb_table.query(pk="BATCH#1", limit=2)
        assert len(results) == 2

    @mock_aws
    def test_batch_write(self, dynamodb_table):
        """batch_write() writes multiple items in a single batch."""
        items = [{"pk": "BATCH#1", "sk": f"ITEM#{i:04d}", "value": f"val-{i}"} for i in range(5)]
        dynamodb_table.batch_write(items)

        results = dynamodb_table.query(pk="BATCH#1")
        assert len(results) == 5
        values = {r["value"] for r in results}
        assert values == {"val-0", "val-1", "val-2", "val-3", "val-4"}

    @mock_aws
    def test_update_item_empty_updates(self, dynamodb_table):
        """update_item() with empty updates dict returns early, no DynamoDB call."""
        dynamodb_table.put_item({"pk": "UPD#1", "sk": "META", "val": "original"})

        # Should not raise and should not modify the item
        dynamodb_table.update_item(pk="UPD#1", sk="META", updates={})

        result = dynamodb_table.get_item(pk="UPD#1", sk="META")
        assert result["val"] == "original"
