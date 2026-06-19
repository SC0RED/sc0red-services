"""Portfolio company discovery step.

Runs two sequential discovery paths on the same scraped data:
1. Heuristic: scrape + filter links with context-aware CTA handling
2. AI extraction: send page text to LLM for structured company extraction

Results merged by normalized URL key (host + path): intersection auto-included,
remainder passed to downstream validation step.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

import jsonschema
from signalfield_core.exceptions.base import EngineError
from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManagerError

from src.data_strategies.portfolio_discovery_strategy import PortfolioDiscoveryStrategy
from src.pipeline.pipeline_steps.ai_call import run_grounded_ai_call, run_structured_ai_call
from src.pipeline.prompts.loader import load_schema, load_system_prompt, load_template

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

# Truncation budgets for the AI extraction prompt. These govern how much of
# the scraped page is visible to the LLM — too small and large portfolios
# (70+ companies) get truncated mid-list. Well under GPT-4o's 128k context.
_AI_LINKS_TEXT_BUDGET = 10_000
_AI_LINK_COUNT_BUDGET = 300
# Combined content budget for the AI extraction prompt. Larger than the visible
# page-text budget because embedded-JSON portfolios live in a dense ~200K script
# island (script_text is prioritised ahead of the page skeleton). Only bites for
# script-embedded sites; plain-text pages stay well under it. ~50K tokens — fine
# for the once-per-firm discovery call.
_AI_CONTENT_BUDGET = 200_000

# Low-water mark: when site-derived discovery finds this many companies OR FEWER,
# run the web-search fallback to recover the firm's portfolio (the site is opaque
# / client-side-only / not embedding its list). Default 0 = rescue only total
# failures; raise to also catch thin/partial scrapes once we've seen real data.
_FALLBACK_THRESHOLD = 0


def _normalize_url_key(url: str) -> str:
    """Normalize a URL to a dedup key of ``host + path``.

    Strips ``www.`` and trailing slash, lowercases the host, ignores query and
    fragment. Path-aware on purpose: a firm's per-company detail pages
    (``firm.com/portfolio/a``, ``firm.com/portfolio/b``) share a domain but are
    distinct companies, so keying on the domain alone would collapse a whole
    portfolio into one. ``www``/trailing-slash variants of the *same* URL still
    map to the same key, and root-path company sites key to just the host — so
    external-company matching (heuristic ∩ AI auto-include) is unchanged.
    """
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    # Lowercase the path too: detail-page slugs are case-insensitive in
    # practice, so two sources emitting different casing dedup to one key.
    path = parsed.path.lower().rstrip("/")
    return f"{host}{path}"


def _merge_results(
    heuristic: list[dict[str, str]],
    ai_extracted: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Merge heuristic and AI results by normalized URL key (host + path).

    Returns ``(auto_included, needs_validation)``:
    - ``auto_included``: companies found by BOTH paths (high confidence, skip AI validation)
    - ``needs_validation``: companies found by only one path (require AI validation)

    Deduplicates by normalized URL key (host + path), so distinct same-domain
    detail pages are kept as distinct companies.
    """
    heuristic_by_key = {_normalize_url_key(c["url"]): c for c in heuristic}
    ai_by_key = {_normalize_url_key(c["url"]): c for c in ai_extracted}

    intersection = set(heuristic_by_key) & set(ai_by_key)
    remainder_keys = (set(heuristic_by_key) | set(ai_by_key)) - intersection

    auto_included = [heuristic_by_key[k] for k in intersection]
    needs_validation = [
        (heuristic_by_key if k in heuristic_by_key else ai_by_key)[k] for k in remainder_keys
    ]

    logger.info(
        "Merge: heuristic=%d, ai=%d, intersection=%d, remainder=%d, total=%d",
        len(heuristic),
        len(ai_extracted),
        len(intersection),
        len(needs_validation),
        len(auto_included) + len(needs_validation),
    )
    return auto_included, needs_validation


def _merge_fallback(
    auto_included: list[dict[str, str]],
    needs_validation: list[dict[str, str]],
    fallback: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Union web-search fallback candidates into ``needs_validation`` only.

    Model-sourced candidates always require validation (never ``auto_included``).
    Deduplicated by normalized URL key against the existing site-derived results,
    so the fallback only ADDS companies the site did not surface.
    """
    seen = {_normalize_url_key(c["url"]) for c in (*auto_included, *needs_validation)}
    merged = list(needs_validation)
    for company in fallback:
        # ``name``/``url`` are schema-required on the web-search response, so
        # access them directly — a missing key is a schema violation, not a
        # default-to-empty case.
        key = _normalize_url_key(company["url"])
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append({"name": company["name"], "url": company["url"], "description": ""})
    return merged


class DiscoverPortfolio(RequestStep):
    """Discovers portfolio companies using heuristic + AI extraction paths."""

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def _require_ai_factory(self) -> AIClientFactory:
        """Return the AI client factory, failing fast if absent.

        The AI extraction and web-search fallback both run only inside an
        ``if self._ai_client_factory`` guard in :meth:`execute`, so a missing
        factory here is a programming error — surface it loudly rather than
        passing ``None`` into the AI call.
        """
        if self._ai_client_factory is None:
            message = "DiscoverPortfolio requires an AI client factory for this path"
            raise RuntimeError(message)
        return self._ai_client_factory

    def execute(self) -> None:
        """Run heuristic + AI discovery and merge results."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        url = accessor.company.url

        if not url:
            message = "No URL provided for portfolio discovery"
            raise ValueError(message)

        # Path 1: Heuristic discovery (also captures page text + links)
        strategy = PortfolioDiscoveryStrategy({"url": url})
        _raw, metadata = strategy.execute()
        heuristic_companies = metadata["companies"]

        # Path 2: AI extraction reuses scraped data (no duplicate HTTP requests)
        ai_companies: list[dict[str, str]] = []
        diagnostic = ""
        is_pe_firm = True  # assume PE unless the extractor says otherwise

        if self._ai_client_factory:
            page_text = metadata.get("page_text", "")
            script_text = metadata.get("script_text", "")
            page_links = metadata.get("all_links", [])
            if page_text or script_text:
                ai_result = self._run_ai_extraction(url, page_text, script_text, page_links)
                ai_companies = ai_result.get("companies", [])
                is_pe_firm = ai_result.get("is_pe_firm", True)
                if not is_pe_firm:
                    diagnostic = ai_result.get(
                        "firm_type_description",
                        "This does not appear to be a PE/VC firm.",
                    )

        # Merge into auto-included (intersection, high confidence) and
        # needs-validation (remainder, only one path found it).
        if heuristic_companies or ai_companies:
            auto_included, needs_validation = _merge_results(heuristic_companies, ai_companies)
        else:
            auto_included, needs_validation = [], []

        # Site-first, fallback-on-low-yield: when the firm's own site yields too
        # few companies (opaque / client-side-only / non-embedding), recover the
        # portfolio via web search. Strictly additive — fallback candidates enter
        # the needs-validation tier only, never auto-included.
        site_total = len(auto_included) + len(needs_validation)
        if self._ai_client_factory and is_pe_firm and site_total <= _FALLBACK_THRESHOLD:
            # Surface WHY we're falling back: a fetch failure means a scrapeable
            # site was unreachable this run (result may be incomplete), vs a
            # genuinely empty/opaque site where web search is the right recovery.
            if metadata.get("site_fetch_failed"):
                logger.warning(
                    "Site fetch failed for %s — falling back to web search; "
                    "result may be incomplete",
                    url,
                )
            else:
                logger.info("Site yielded no companies for %s — using web-search fallback", url)
            # Seed with on-site logo-grid names when present (e.g. Vista): the
            # site supplies the authoritative WHO, web search resolves the URLs.
            seed_names = metadata.get("logo_company_names", [])
            fallback = self._run_web_search_fallback(url, seed_names)
            needs_validation = _merge_fallback(auto_included, needs_validation, fallback)

        if not (auto_included or needs_validation) and not diagnostic:
            diagnostic = "Could not identify portfolio companies from this website."

        total = len(auto_included) + len(needs_validation)
        logger.info(
            "Discovered %d companies from %s (heuristic=%d, ai=%d, "
            "auto_included=%d, needs_validation=%d)",
            total,
            url,
            len(heuristic_companies),
            len(ai_companies),
            len(auto_included),
            len(needs_validation),
        )

        # ``portfolio_companies`` carries only the remainder that needs AI
        # validation. ``portfolio_auto_included`` is merged back in by
        # ``ValidatePortfolioCompanies`` after validation completes.
        self.request_executor.add_details(
            {
                "portfolio_companies": needs_validation,
                "portfolio_auto_included": auto_included,
                "portfolio_companies_json": json.dumps(auto_included + needs_validation),
                "portfolio_count": total,
                "portfolio_diagnostic": diagnostic,
            }
        )
        self.request_executor.mark_question_complete("discover_portfolio")

    def _run_ai_extraction(
        self,
        firm_url: str,
        page_text: str,
        script_text: str,
        links: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send scraped content to AI for structured company extraction.

        Prioritises ``script_text`` (the data-bearing inline JSON where SSR sites
        embed the portfolio) ahead of the visible ``page_text`` skeleton, within
        the same budget — so embedded-JSON portfolios are extractable while
        anchor/text portfolios still work.
        """
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
            firm_url=firm_url,
            page_text=content[:_AI_CONTENT_BUDGET],
            links_text=links_text[:_AI_LINKS_TEXT_BUDGET],
        )
        # ``_tokens`` is the 4th tuple element from run_structured_ai_call
        # (added 2026-05-15). DiscoverPortfolio doesn't surface token
        # telemetry yet; opt-in later if needed.
        _label, result, _elapsed, _tokens = run_structured_ai_call(
            ai_client_factory=self._require_ai_factory(),
            user_prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            label="extract_portfolio",
            step_name="DiscoverPortfolio",
        )
        return result

    def _run_web_search_fallback(
        self,
        firm_url: str,
        seed_names: list[str] | None = None,
    ) -> list[dict[str, str]]:
        """Recover the firm's portfolio via web search when the site is opaque.

        When ``seed_names`` is provided (e.g. names read from a logo grid), the
        prompt is seeded with them so the model resolves their official URLs
        rather than recalling the portfolio from scratch.

        Fail-soft: a search/AI failure (or empty result) yields no candidates and
        never crashes the scan — only programming errors propagate. Results are
        model-sourced candidates that the downstream validation step confirms.
        """
        template = load_template("discover_portfolio_websearch")
        schema = load_schema("discover_portfolio_websearch")
        system_prompt = load_system_prompt("portfolio_validation")
        if seed_names:
            known = ", ".join(seed_names)
            known_block = (
                "The firm's portfolio is known to include these companies "
                f"(found on its own site): {known}.\n"
                "Return each of these companies' official website URL, and add "
                "any other current holdings you find."
            )
        else:
            known_block = ""
        prompt = template.format(firm_url=firm_url, known_companies=known_block)
        try:
            _label, content, _elapsed, _tokens, _sources = run_grounded_ai_call(
                ai_client_factory=self._require_ai_factory(),
                user_prompt=prompt,
                schema=schema,
                system_prompt=system_prompt,
                label="portfolio_web_fallback",
                step_name="DiscoverPortfolio",
            )
        except (
            EngineError,
            FutureManagerError,
            jsonschema.ValidationError,
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
        ):
            # Fail-soft: a search failure or a malformed (schema-invalid) AI
            # response yields no extra candidates — the scan continues on the
            # site-derived results rather than crashing.
            logger.exception(
                "[DiscoverPortfolio] web-search fallback failed for %s; "
                "continuing with site results",
                firm_url,
            )
            return []
        companies = content["companies"]
        logger.info(
            "[DiscoverPortfolio] web-search fallback recovered %d candidate(s) for %s",
            len(companies),
            firm_url,
        )
        return companies
