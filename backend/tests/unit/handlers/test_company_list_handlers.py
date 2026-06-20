"""Tests for the stateless company-list parse handler."""

import base64
import json

from src.handlers.auth_middleware import AuthContext
from src.handlers.company_list_handlers import handle_parse_company_list


def _auth() -> AuthContext:
    return AuthContext(user_id="user-1", org_id="org-1", email="a@b.com", role="analyst")


def _event(file_type: str, raw: bytes) -> dict[str, object]:
    return {
        "body": json.dumps({"fileType": file_type, "fileContent": base64.b64encode(raw).decode()})
    }


class TestHandleParseCompanyList:
    def test_parses_csv_and_reports_counts(self):
        event = _event("csv", b"name,url\nAcme,https://acme.com\nBeta,\n")
        result = handle_parse_company_list(event, _auth())
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["count"] == 2
        assert body["withUrl"] == 1
        assert body["needsUrl"] == 1
        assert body["companies"][0] == {"name": "Acme", "url": "https://acme.com"}

    def test_missing_fields_is_400(self):
        result = handle_parse_company_list({"body": json.dumps({"fileType": "csv"})}, _auth())
        assert result["statusCode"] == 400
        assert json.loads(result["body"])["code"] == "VALIDATION_ERROR"

    def test_empty_string_fields_is_400(self):
        event = {"body": json.dumps({"fileType": "", "fileContent": ""})}
        result = handle_parse_company_list(event, _auth())
        assert result["statusCode"] == 400
        assert "required" in json.loads(result["body"])["error"]

    def test_unsupported_type_is_400(self):
        event = _event("exe", b"data")
        result = handle_parse_company_list(event, _auth())
        assert result["statusCode"] == 400
        assert "Unsupported file type" in json.loads(result["body"])["error"]

    def test_spreadsheet_type_is_400(self):
        event = _event("xlsx", b"name,url\nAcme,https://acme.com\n")
        result = handle_parse_company_list(event, _auth())
        assert result["statusCode"] == 400
        assert "Unsupported file type" in json.loads(result["body"])["error"]

    def test_malformed_json_body_is_400(self):
        result = handle_parse_company_list({"body": "{not json"}, _auth())
        assert result["statusCode"] == 400
        assert json.loads(result["body"])["code"] == "VALIDATION_ERROR"

    def test_non_object_json_body_is_400(self):
        for raw_body in ("null", "[]", '"string"', "42"):
            result = handle_parse_company_list({"body": raw_body}, _auth())
            assert result["statusCode"] == 400, raw_body
            assert "JSON object" in json.loads(result["body"])["error"]

    def test_non_string_fields_is_400(self):
        event = {"body": json.dumps({"fileType": 123, "fileContent": ["x"]})}
        result = handle_parse_company_list(event, _auth())
        assert result["statusCode"] == 400
        assert "must be strings" in json.loads(result["body"])["error"]

    def test_corrupt_pdf_is_400(self):
        event = _event("pdf", b"%PDF-1.4 not really a pdf")
        result = handle_parse_company_list(event, _auth())
        assert result["statusCode"] == 400
        assert json.loads(result["body"])["code"] == "VALIDATION_ERROR"

    def test_invalid_base64_is_400(self):
        event = {"body": json.dumps({"fileType": "csv", "fileContent": "not base64!!!"})}
        result = handle_parse_company_list(event, _auth())
        assert result["statusCode"] == 400
        assert "base64" in json.loads(result["body"])["error"]

    def test_empty_file_is_400(self):
        event = _event("csv", b"\n\n")
        result = handle_parse_company_list(event, _auth())
        assert result["statusCode"] == 400
        assert "No companies found" in json.loads(result["body"])["error"]
