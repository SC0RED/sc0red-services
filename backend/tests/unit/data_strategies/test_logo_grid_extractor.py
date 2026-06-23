"""Tests for logo-grid company-name extraction."""

from bs4 import BeautifulSoup

from src.data_strategies.logo_grid_extractor import extract_logo_companies


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_extracts_logo_of_company_names():
    html = """
    <html><body>
      <img src="/jamf.svg" alt="Logo of software company Jamf">
      <img src="/datto.svg" alt="Logo of software company Datto.">
      <img src="/kb4.svg" alt="Logo of company KnowBe4">
    </body></html>
    """
    out = extract_logo_companies(_soup(html))
    assert out == ["Jamf", "Datto", "KnowBe4"]


def test_extracts_multiword_descriptor_before_company():
    html = """
    <html><body>
      <img alt="Logo of cloud software company Jamf">
      <img alt="Logo of the company Okta">
    </body></html>
    """
    assert extract_logo_companies(_soup(html)) == ["Jamf", "Okta"]


def test_excludes_firm_and_non_company_logos():
    # No "company" keyword → not a portfolio company logo.
    html = """
    <html><body>
      <img alt="Vista logo">
      <img alt="Partner badge">
      <img src="/acme.svg" alt="Logo of enterprise company Acme">
    </body></html>
    """
    assert extract_logo_companies(_soup(html)) == ["Acme"]


def test_dedupes_case_insensitively():
    html = """
    <html><body>
      <img alt="Logo of software company Acme">
      <img alt="Logo of software company ACME">
    </body></html>
    """
    assert extract_logo_companies(_soup(html)) == ["Acme"]


def test_no_logo_grid_returns_empty():
    html = "<html><body><img alt=''><img alt='hero image'><p>text</p></body></html>"
    assert extract_logo_companies(_soup(html)) == []


def test_length_bounds():
    html = (
        "<html><body>"
        '<img alt="Logo of software company A">'  # too short (1 char)
        f'<img alt="Logo of software company {"x" * 80}">'  # too long
        '<img alt="Logo of software company Okta">'
        "</body></html>"
    )
    assert extract_logo_companies(_soup(html)) == ["Okta"]
