"""Tests for customer company-list parsing (CSV + best-effort document)."""

import pytest

from src.documents.parse_company_list import parse_company_list


class TestParseCsv:
    def test_name_and_url_columns(self):
        content = b"name,url\nAcme Corp,https://acme.com\nBeta Inc,beta.io\n"
        result = parse_company_list(content, "csv")
        assert result == [
            {"name": "Acme Corp", "url": "https://acme.com"},
            {"name": "Beta Inc", "url": "https://beta.io"},
        ]

    def test_name_only_leaves_url_empty(self):
        content = b"company\nAcme Corp\nBeta Inc\n"
        result = parse_company_list(content, "csv")
        assert result == [
            {"name": "Acme Corp", "url": ""},
            {"name": "Beta Inc", "url": ""},
        ]

    def test_alternate_header_names(self):
        content = b"Portfolio Company,Website\nAcme,www.acme.com\n"
        result = parse_company_list(content, "csv")
        assert result == [{"name": "Acme", "url": "https://www.acme.com"}]

    def test_no_recognizable_header_treats_first_cell_as_name(self):
        content = b"Acme,https://acme.com\nBeta,beta.io\n"
        result = parse_company_list(content, "csv")
        # Every row (including the first) is a company; URL scavenged from row.
        assert result == [
            {"name": "Acme", "url": "https://acme.com"},
            {"name": "Beta", "url": "https://beta.io"},
        ]

    def test_strips_utf8_bom_and_blank_rows(self):
        content = "﻿name,url\nAcme,https://acme.com\n\n  ,  \n".encode()
        result = parse_company_list(content, "csv")
        assert result == [{"name": "Acme", "url": "https://acme.com"}]

    def test_deduplicates_by_name_case_insensitively(self):
        content = b"name,url\nAcme,https://acme.com\nacme,https://other.com\n"
        result = parse_company_list(content, "csv")
        assert result == [{"name": "Acme", "url": "https://acme.com"}]

    def test_non_url_cell_is_dropped(self):
        content = b"name,url\nAcme,not a url\n"
        result = parse_company_list(content, "csv")
        assert result == [{"name": "Acme", "url": ""}]

    def test_name_header_without_url_column(self):
        content = b"name\nAcme\nBeta\n"
        result = parse_company_list(content, "csv")
        assert result == [{"name": "Acme", "url": ""}, {"name": "Beta", "url": ""}]

    def test_row_with_blank_name_cell_is_skipped(self):
        content = b"name,url\n ,https://orphan.com\nAcme,https://acme.com\n"
        result = parse_company_list(content, "csv")
        assert result == [{"name": "Acme", "url": "https://acme.com"}]

    def test_ragged_row_shorter_than_name_column_is_skipped(self):
        content = b"first,name,url\nlonely\nx,Acme,https://acme.com\n"
        result = parse_company_list(content, "csv")
        assert result == [{"name": "Acme", "url": "https://acme.com"}]

    def test_row_missing_trailing_url_cell(self):
        content = b"name,url\nAcme\nBeta,https://beta.com\n"
        result = parse_company_list(content, "csv")
        assert result == [
            {"name": "Acme", "url": ""},
            {"name": "Beta", "url": "https://beta.com"},
        ]

    def test_no_header_row_without_url(self):
        content = b"Acme,software\nBeta,services\n"
        result = parse_company_list(content, "csv")
        assert result == [{"name": "Acme", "url": ""}, {"name": "Beta", "url": ""}]

    def test_caps_at_max_companies(self):
        from src.documents.parse_company_list import _MAX_COMPANIES

        rows = "\n".join(f"Company {index}" for index in range(_MAX_COMPANIES + 50))
        content = f"name\n{rows}\n".encode()
        result = parse_company_list(content, "csv")
        assert len(result) == _MAX_COMPANIES

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError, match="No companies found"):
            parse_company_list(b"\n\n", "csv")


class TestParseDocument:
    def test_plain_text_one_company_per_line(self):
        content = b"Acme Corp\nBeta Inc\nGamma LLC\n"
        result = parse_company_list(content, "txt")
        assert [c["name"] for c in result] == ["Acme Corp", "Beta Inc", "Gamma LLC"]
        assert all(c["url"] == "" for c in result)

    def test_strips_bullet_markers(self):
        content = b"- Acme Corp\n* Beta Inc\n\xe2\x80\xa2 Gamma LLC\n"
        result = parse_company_list(content, "txt")
        assert [c["name"] for c in result] == ["Acme Corp", "Beta Inc", "Gamma LLC"]

    def test_extracts_inline_url(self):
        content = b"Acme Corp - https://acme.com\nBeta Inc\n"
        result = parse_company_list(content, "txt")
        assert result == [
            {"name": "Acme Corp", "url": "https://acme.com"},
            {"name": "Beta Inc", "url": ""},
        ]

    def test_scavenges_bare_domain_from_text(self):
        content = b"Acme Corp acme.com\nBeta Inc, beta.io\n"
        result = parse_company_list(content, "txt")
        assert result == [
            {"name": "Acme Corp", "url": "https://acme.com"},
            {"name": "Beta Inc", "url": "https://beta.io"},
        ]

    def test_lone_domain_stays_as_name(self):
        content = b"acme.com\n"
        result = parse_company_list(content, "txt")
        assert result == [{"name": "acme.com", "url": ""}]

    def test_does_not_mistake_abbreviation_for_domain(self):
        # "U.S." matches a loose domain pattern but has a 1-char TLD — it must
        # stay part of the name, not be promoted to a URL.
        content = b"Acme U.S. Holdings\n"
        result = parse_company_list(content, "txt")
        assert result == [{"name": "Acme U.S. Holdings", "url": ""}]

    def test_bare_url_only_line_is_skipped(self):
        content = b"https://acme.com\nBeta Inc\n"
        result = parse_company_list(content, "txt")
        assert result == [{"name": "Beta Inc", "url": ""}]

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported company-list type"):
            parse_company_list(b"data", "exe")

    def test_spreadsheet_types_rejected(self):
        # xlsx/xls are excluded: extract_text emits sheet headers + joined
        # cells that would become junk candidates — customers export to CSV.
        for file_type in ("xlsx", "xls"):
            with pytest.raises(ValueError, match="Unsupported company-list type"):
                parse_company_list(b"data", file_type)

    def test_blank_document_raises(self):
        with pytest.raises(ValueError, match="No companies found"):
            parse_company_list(b"   \n\n   \n", "txt")
