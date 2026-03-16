"""Stage 1: AI profile extraction.

Ports buildProfilePrompt from pe-scan/src/lib/ai/prompts.ts:42-65.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep

from src.documents.extract_text import MAX_CHARS_COMBINED
from src.models.model_company import CompanyProfile
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior business intelligence analyst specializing in technology companies "
    "and private equity portfolio analysis. Your job is to extract structured, accurate "
    "information about a company from raw web content."
)

_USER_PROMPT_TEMPLATE = """Analyze this company website content and extract a structured company profile.

URL: {url}

Website Content:
{content}
{document_section}
Extract the company profile with all available fields."""

_PROFILE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string", "description": "Official company name"},
        "industry": {
            "type": "string",
            "description": "Primary industry (be specific, e.g. 'B2B SaaS - HR Technology' not just 'Software')",
        },
        "industry_sector": {
            "type": "string",
            "description": "Broader sector (Technology, Healthcare, Financial Services, Manufacturing, Retail, Real Estate, Media, Professional Services, Energy, Transportation, etc.)",
        },
        "business_model": {
            "type": "string",
            "description": "How they make money (SaaS, marketplace, services, product, etc.)",
        },
        "description": {
            "type": "string",
            "description": "2-3 sentence description of what they do",
        },
        "products_services": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific products or services",
        },
        "target_market": {"type": "string", "description": "Who their customers are"},
        "company_size": {
            "type": "string",
            "description": "Estimated size (Startup <50, Small 50-200, Mid-market 200-1000, Enterprise 1000+)",
        },
        "revenue_model": {
            "type": "string",
            "description": "Subscription, transaction, professional services, etc.",
        },
        "tech_signals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Technology signals from job postings, tech stack mentions, integrations",
        },
        "competitive_positioning": {"type": "string", "description": "How they differentiate"},
        "ai_maturity": {
            "type": "string",
            "description": "Current AI adoption level (None evident, Early exploration, Partial adoption, AI-forward)",
        },
        "key_risks_visible": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Obvious risk signals visible on the site",
        },
    },
    "required": [
        "company_name",
        "industry",
        "industry_sector",
        "business_model",
        "description",
        "products_services",
        "target_market",
        "company_size",
        "revenue_model",
        "tech_signals",
        "competitive_positioning",
        "ai_maturity",
        "key_risks_visible",
    ],
    "additionalProperties": False,
}


class ExtractProfile(RequestStep):
    """Extracts a structured CompanyProfile from scraped website content."""

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Extract a structured company profile from scraped website content."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        scraped_text = accessor.get_scraped_text()
        actual_url = accessor.company.actual_url or accessor.company.url

        document_text = accessor.get_document_text()
        document_section = ""
        if document_text:
            document_section = (
                "\nSUPPLEMENTARY DOCUMENTS (investment memos, diligence docs, etc.):\n"
                f"{document_text[:MAX_CHARS_COMBINED]}\n"
            )

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            url=actual_url,
            content=scraped_text[:12000],
            document_section=document_section,
        )

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        timer = StepTimer("ExtractProfile")

        client = self._ai_client_factory.get_client(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=_SYSTEM_PROMPT,
        )
        logger.info(
            "[ExtractProfile] sending AI request: prompt_len=%d, model=%s",
            len(user_prompt),
            getattr(client, "model", "unknown"),
        )
        with timer.measure("ai_call"):
            try:
                response = client.query_structured(input_text=user_prompt, json_schema=_PROFILE_SCHEMA)
            except Exception:
                logger.exception("[ExtractProfile] AI request failed")
                raise
        logger.info(
            "[ExtractProfile] AI response received: metadata=%s",
            response.metadata,
        )
        data = response.content

        profile = CompanyProfile(**data)

        if not profile.company_name or not profile.industry:
            message = (
                "Profile extraction returned incomplete data — company_name or industry missing"
            )
            raise ValueError(message)

        accessor.set_profile(profile)
        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("extract_profile")
