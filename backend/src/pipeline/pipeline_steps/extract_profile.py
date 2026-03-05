"""Stage 1: AI profile extraction.

Ports buildProfilePrompt from pe-scan/src/lib/ai/prompts.ts:42-65.
"""

from __future__ import annotations

import logging

import openai

from signalfield_core.pipeline.step import RequestStep

from src.facades.company_accessor import CompanyAccessor
from src.models.model_company import CompanyProfile
from src.utilities.json_utils import parse_json_response

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior business intelligence analyst specializing in technology companies "
    "and private equity portfolio analysis. Your job is to extract structured, accurate "
    "information about a company from raw web content.\n\n"
    "Always respond with valid JSON only. No markdown, no explanation text outside the JSON."
)

_USER_PROMPT_TEMPLATE = """Analyze this company website content and extract a structured company profile.

URL: {url}

Website Content:
{content}

Respond with this exact JSON structure:
{{
  "company_name": "string - official company name",
  "industry": "string - primary industry (be specific, e.g. 'B2B SaaS - HR Technology' not just 'Software')",
  "industry_sector": "string - broader sector (Technology, Healthcare, Financial Services, Manufacturing, Retail, Real Estate, Media, Professional Services, Energy, Transportation, etc.)",
  "business_model": "string - how they make money (SaaS, marketplace, services, product, etc.)",
  "description": "string - 2-3 sentence description of what they do",
  "products_services": ["array of specific products or services"],
  "target_market": "string - who their customers are",
  "company_size": "string - estimated size (Startup <50, Small 50-200, Mid-market 200-1000, Enterprise 1000+)",
  "revenue_model": "string - subscription, transaction, professional services, etc.",
  "tech_signals": ["array of technology signals from job postings, tech stack mentions, integrations"],
  "competitive_positioning": "string - how they differentiate",
  "ai_maturity": "string - current AI adoption level (None evident, Early exploration, Partial adoption, AI-forward)",
  "key_risks_visible": ["array of obvious risk signals visible on the site"]
}}"""


class ExtractProfile(RequestStep):
    """Extracts a structured CompanyProfile from scraped website content."""

    def __init__(self, openai_api_key: str = "", model: str = "gpt-4o") -> None:
        super().__init__()
        self._openai_api_key = openai_api_key
        self._model = model

    def execute(self) -> None:
        accessor: CompanyAccessor = self.entity_accessor  # type: ignore[assignment]
        scraped_text = accessor.get_scraped_text()
        actual_url = accessor.company.actual_url or accessor.company.url

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            url=actual_url,
            content=scraped_text[:12000],
        )

        client = openai.OpenAI(api_key=self._openai_api_key)
        response = client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content or ""
        data = parse_json_response(content)
        profile = CompanyProfile(**data)

        if not profile.company_name or not profile.industry:
            msg = "Profile extraction returned incomplete data — company_name or industry missing"
            raise ValueError(msg)

        accessor.set_profile(profile)
        self.request_executor.mark_question_complete("extract_profile")


