"""Tests for DynamoDB client utilities."""

from decimal import Decimal

from src.repositories.dynamodb.client import _convert_floats


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
