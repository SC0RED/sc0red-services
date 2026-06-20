"""Parse a customer-provided company list (CSV or document) into scan candidates.

When automatic portfolio discovery comes up short, the confirmation screen lets
a customer upload a CSV/PDF of their firm's holdings. This module turns the raw
file into ``{"name", "url"}`` candidates that the customer merges into the
editable confirmation list and scans via the existing confirm path.

CSV is parsed structurally — a ``name`` column is required, a URL column is
optional. Other document types fall back to a best-effort one-company-per-line
read via :func:`extract_text`. Either way the result is deduplicated by name;
``url`` is left "" when the source did not supply one (the customer resolves it
on the confirmation screen, or a later step does).
"""

from __future__ import annotations

import csv
import io
import re

from src.documents.extract_text import extract_text

# Types this endpoint accepts. A deliberate subset of extract_text's
# SUPPORTED_TYPES: spreadsheets (xlsx/xls) are excluded because extract_text
# emits "[Sheet: …]" headers and comma-joined cells that the best-effort
# line reader would turn into junk candidates — customers export those to CSV,
# which is parsed structurally below. Structured spreadsheet parsing is a
# possible later slice.
SUPPORTED_LIST_TYPES = frozenset({"csv", "pdf", "docx", "txt", "md"})

_NAME_HEADERS = frozenset({"name", "company", "company name", "companyname", "portfolio company"})
_URL_HEADERS = frozenset({"url", "website", "company url", "companyurl", "domain", "site", "link"})
# Guard against a pathological upload turning into an unbounded candidate list.
_MAX_COMPANIES = 1000

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_DOMAIN_PATTERN = re.compile(r"^[\w-]+(?:\.[\w-]+)+(?:/\S*)?$")
# Leading bullet / list markers stripped from best-effort document lines.
_LINE_NOISE = " \t•*–-—|,;:"  # noqa: RUF001  intentional unicode bullet/dash markers


def parse_company_list(file_bytes: bytes, file_type: str) -> list[dict[str, str]]:
    """Parse uploaded file bytes into deduplicated company candidates.

    Args:
        file_bytes: Raw uploaded file content.
        file_type: File extension without a dot (e.g. ``"csv"``, ``"pdf"``).

    Returns:
        Candidates ``[{"name": str, "url": str}]`` in first-seen order,
        deduplicated by lowercased name. ``url`` is "" when none was found.

    Raises:
        ValueError: If the file type is unsupported or no companies parse out.
    """
    normalized = file_type.lower().strip(".")
    if normalized not in SUPPORTED_LIST_TYPES:
        supported = ", ".join(sorted(SUPPORTED_LIST_TYPES))
        message = f"Unsupported company-list type: {normalized}. Supported: {supported}"
        raise ValueError(message)

    if normalized == "csv":
        rows = _parse_csv(file_bytes)
    else:
        rows = _parse_lines(extract_text(file_bytes, normalized))

    candidates = _remove_duplicates(rows)
    if not candidates:
        message = "No companies found in the uploaded file"
        raise ValueError(message)
    return candidates


def _parse_csv(file_bytes: bytes) -> list[dict[str, str]]:
    """Parse CSV bytes into ``{name, url}`` rows using header detection."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    rows = [row for row in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in row)]
    if not rows:
        return []

    header = [cell.strip().lower() for cell in rows[0]]
    name_index = _find_column_index(header, _NAME_HEADERS)
    if name_index is None:
        # No recognizable header — treat the first cell of every row as a
        # company name and scavenge a URL from anywhere else on the row.
        return [
            {"name": row[0].strip(), "url": _extract_first_url(row)}
            for row in rows
            if row and row[0].strip()
        ]

    url_index = _find_column_index(header, _URL_HEADERS)
    parsed: list[dict[str, str]] = []
    for row in rows[1:]:
        if name_index >= len(row) or not row[name_index].strip():
            continue
        raw_url = row[url_index].strip() if url_index is not None and url_index < len(row) else ""
        parsed.append({"name": row[name_index].strip(), "url": _normalize_url(raw_url)})
    return parsed


def _parse_lines(text: str) -> list[dict[str, str]]:
    """Best-effort: one company per non-empty line of extracted document text."""
    parsed: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().strip(_LINE_NOISE).strip()
        if not line:
            continue
        url = ""
        match = _URL_PATTERN.search(line)
        if match:
            url = match.group(0).rstrip(".,);")
            line = line[: match.start()].strip().strip(_LINE_NOISE).strip()
        if line:
            parsed.append({"name": line, "url": url})
    return parsed


def _find_column_index(header: list[str], candidates: frozenset[str]) -> int | None:
    """Return the index of the first header cell matching ``candidates``."""
    for index, cell in enumerate(header):
        if cell in candidates:
            return index
    return None


def _extract_first_url(row: list[str]) -> str:
    """Return the first cell of ``row`` that normalizes to an http(s) URL."""
    for cell in row:
        url = _normalize_url(cell.strip())
        if url:
            return url
    return ""


def _normalize_url(value: str) -> str:
    """Return an http(s) URL for ``value``, or "" if it is not URL-like.

    Bare domains (``example.com``) are promoted to ``https://`` so they satisfy
    the confirm path's http(s) requirement; non-URL text returns "".
    """
    value = value.strip()
    if not value:
        return ""
    if value.lower().startswith(("http://", "https://")):
        return value
    if _DOMAIN_PATTERN.match(value):
        return f"https://{value}"
    return ""


def _remove_duplicates(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Deduplicate by lowercased name, preserving first-seen order and cap."""
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for row in rows:
        name = row["name"].strip()
        key = name.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append({"name": name, "url": row["url"]})
        if len(result) >= _MAX_COMPANIES:
            break
    return result
