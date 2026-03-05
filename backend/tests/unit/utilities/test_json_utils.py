"""Tests for JSON parsing utility."""

import pytest

from src.utilities.json_utils import parse_json_response


class TestParseJsonResponse:
    def test_parse_clean_json(self):
        result = parse_json_response('{"name": "Acme", "score": 7}')
        assert result["name"] == "Acme"
        assert result["score"] == 7

    def test_parse_json_with_markdown_wrapper(self):
        text = '```json\n{"name": "Acme"}\n```'
        result = parse_json_response(text)
        assert result["name"] == "Acme"

    def test_parse_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"company": "Test Corp"}\nDone.'
        result = parse_json_response(text)
        assert result["company"] == "Test Corp"

    def test_parse_nested_json(self):
        text = '{"scores": [{"cat": "risk", "val": 5}], "total": 5}'
        result = parse_json_response(text)
        assert len(result["scores"]) == 1
        assert result["total"] == 5

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="No JSON"):
            parse_json_response("")

    def test_no_json_raises(self):
        with pytest.raises(ValueError, match="No JSON"):
            parse_json_response("This is just plain text with no braces.")

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            parse_json_response("{invalid json content}")
