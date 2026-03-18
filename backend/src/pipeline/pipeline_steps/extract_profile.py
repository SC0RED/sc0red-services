"""Profile extraction constants — system prompt, schema, and prompt template.

Used by ParallelProfileRiskAndIdeation to build the profile extraction AI call.
"""

from __future__ import annotations

PROFILE_SYSTEM_PROMPT = (
    "You are a senior business intelligence analyst specializing in technology companies "
    "and private equity portfolio analysis. Your job is to extract structured, accurate "
    "information about a company from raw web content."
)

PROFILE_PROMPT_TEMPLATE = """Analyze this company website content and extract a structured company profile.

URL: {url}

Website Content:
{content}
{document_section}
Extract the company profile with all available fields."""

PROFILE_SCHEMA: dict[str, object] = {
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
