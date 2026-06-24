"""Shared structured AI extraction of portfolio companies from scraped content.

Used by ``DiscoverPortfolio`` (the firm's own site) and ``FetchProvidedSource``
(a customer-supplied reliable URL) so both run the same extraction over the
same scrape output rather than duplicating the prompt/budget handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call
from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

# Truncation budgets for the AI extraction prompt. Govern how much of the
# scraped page is visible to the LLM — too small and large portfolios (70+
# companies) get truncated mid-list. ``script_text`` (the data-bearing inline
# JSON where SSR sites embed the portfolio) is prioritised ahead of the visible
# page skeleton within the same budget, so embedded-JSON portfolios extract.
_AI_LINKS_TEXT_BUDGET = 10_000
_AI_LINK_COUNT_BUDGET = 300
_AI_CONTENT_BUDGET = 200_000


def extract_companies_from_scrape(
    ai_client_factory: AIClientFactory,
    page_url: str,
    page_text: str,
    script_text: str,
    links: list[dict[str, str]],
    *,
    step_name: str,
) -> dict[str, Any]:
    """Send scraped content to the AI for structured company extraction."""
    if script_text and page_text:
        content = f"{script_text}\n\n{page_text}"
    else:
        content = script_text or page_text
    links_text = "\n".join(
        f"- {link['text']}: {link['href']}" for link in links[:_AI_LINK_COUNT_BUDGET]
    )
    template = load_template("extract_portfolio_companies")
    schema = load_schema("extract_portfolio_companies")
    system_prompt = load_system_prompt("portfolio_validation")

    prompt = template.format(
        firm_url=page_url,
        page_text=content[:_AI_CONTENT_BUDGET],
        links_text=links_text[:_AI_LINKS_TEXT_BUDGET],
    )
    _label, result, _elapsed, _tokens = run_structured_ai_call(
        ai_client_factory=ai_client_factory,
        user_prompt=prompt,
        schema=schema,
        system_prompt=system_prompt,
        label="extract_portfolio",
        step_name=step_name,
    )
    return result
