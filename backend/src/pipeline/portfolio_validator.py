"""Validate discovered portfolio companies with a quick AI yes/no check."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are validating whether a URL belongs to a PE firm's portfolio. "
    "Answer only with the structured response."
)

_VALIDATION_PROMPT = (
    'Is "{company_name}" (URL: {company_url}) a portfolio company '
    "or investment of the firm at {firm_url}?\n\n"
    "Consider:\n"
    "- Portfolio companies are companies that the firm has invested in, "
    "acquired, or manages\n"
    "- Links to the firm's own pages (about, team, news, careers) "
    "are NOT portfolio companies\n"
    "- Links to external tools, services, or platforms used by the firm "
    "are NOT portfolio companies\n\n"
    'Answer with ONLY "yes" or "no".'
)

_VALIDATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_portfolio_company": {
            "type": "boolean",
            "description": "true if this is a portfolio company of the firm",
        }
    },
    "required": ["is_portfolio_company"],
    "additionalProperties": False,
}

_MAX_WORKERS = 10


def _validate_single_company(
    company: dict[str, Any],
    firm_url: str,
    ai_client_factory: AIClientFactory,
) -> tuple[dict[str, Any], bool]:
    """Validate a single company. Returns (company, is_valid)."""
    company_name = company.get("name", "unknown")
    company_url = company.get("url", "")

    prompt = _VALIDATION_PROMPT.format(
        company_name=company_name,
        company_url=company_url,
        firm_url=firm_url,
    )

    client = ai_client_factory.get_client(
        verbosity=Verbosity.LOW,
        reasoning_effort=ReasoningEffort.LOW,
        precision=Precision.STANDARD,
        instructions=_SYSTEM_PROMPT,
    )

    response = client.query_structured(
        input_text=prompt,
        json_schema=_VALIDATION_SCHEMA,
    )

    content = response.content
    if isinstance(content, str):
        content = json.loads(content)

    is_valid = bool(content.get("is_portfolio_company", True))
    logger.info(
        "[portfolio_validator] %s (%s): is_portfolio_company=%s",
        company_name,
        company_url,
        is_valid,
    )
    return company, is_valid


def validate_portfolio_companies(
    companies: list[dict[str, Any]],
    firm_url: str,
    ai_client_factory: AIClientFactory,
) -> list[dict[str, Any]]:
    """Validate discovered companies in parallel; keep companies that fail validation."""
    if not companies:
        return companies

    logger.info(
        "[portfolio_validator] validating %d companies against firm %s",
        len(companies),
        firm_url,
    )

    validated: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(companies))) as executor:
        futures = {
            executor.submit(_validate_single_company, company, firm_url, ai_client_factory): company
            for company in companies
        }

        for future in as_completed(futures):
            original_company = futures[future]
            try:
                _company, is_valid = future.result()
                if is_valid:
                    validated.append(_company)
                else:
                    logger.info(
                        "[portfolio_validator] filtered out: %s (%s)",
                        original_company.get("name", "unknown"),
                        original_company.get("url", ""),
                    )
            except Exception:
                logger.exception(
                    "[portfolio_validator] validation failed for %s — keeping company",
                    original_company.get("name", "unknown"),
                )
                validated.append(original_company)

    logger.info(
        "[portfolio_validator] result: %d/%d companies validated",
        len(validated),
        len(companies),
    )
    return validated
