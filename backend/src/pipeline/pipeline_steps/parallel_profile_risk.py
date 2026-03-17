"""Composite step: runs profile extraction and risk assessment AI calls in parallel.

Instead of the sequential ExtractProfile → AssessRisk flow, this step makes both
AI calls concurrently. The risk assessment receives raw scraped text directly
(rather than the structured profile), since the AI is capable of assessing risks
from unstructured content.

Saves ~30-45s of wall-clock time by overlapping the two longest early-pipeline calls.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep

from src.documents.extract_text import MAX_CHARS_COMBINED
from src.models.model_company import CompanyProfile, RiskAssessment, RiskScore
from src.pipeline.pipeline_steps.assess_risk import (
    RISK_ASSESSMENT_QUESTIONS,
    RISK_CATEGORIES_BLOCK,
    RISK_INDUSTRY_WEIGHTING,
    RISK_SCHEMA,
    RISK_SYSTEM_PROMPT,
)
from src.pipeline.pipeline_steps.extract_profile import (
    PROFILE_PROMPT_TEMPLATE,
    PROFILE_SCHEMA,
    PROFILE_SYSTEM_PROMPT,
)
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor

logger = logging.getLogger(__name__)


def _build_risk_prompt_from_text(
    scraped_text: str,
    url: str,
    document_text: str | None = None,
) -> str:
    """Build risk assessment prompt from raw scraped text (no profile needed)."""
    document_section = ""
    if document_text:
        document_section = f"\n\nSUPPLEMENTARY DOCUMENTS:\n{document_text[:MAX_CHARS_COMBINED]}"

    return f"""Perform a comprehensive AI disruption risk assessment for this company.

COMPANY URL: {url}

WEBSITE CONTENT:
{scraped_text[:12000]}{document_section}

RISK CATEGORIES TO ASSESS:
{RISK_CATEGORIES_BLOCK}

INDUSTRY CONTEXT: Based on the company information above, apply industry-specific weighting:
{RISK_INDUSTRY_WEIGHTING}

{RISK_ASSESSMENT_QUESTIONS}"""


class ParallelProfileAndRisk(RequestStep):
    """Runs profile extraction and risk assessment AI calls in parallel.

    Replaces the sequential ExtractProfile → AssessRisk pair in the pipeline.
    Both AI calls receive the same raw scraped text and run concurrently using
    a ThreadPoolExecutor, saving ~30-45s of wall-clock time.
    """

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run profile extraction and risk assessment in parallel."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        scraped_text = accessor.get_scraped_text()
        actual_url = accessor.company.actual_url or accessor.company.url
        document_text = accessor.get_document_text()

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        # Build profile prompt (same as ExtractProfile)
        document_section = ""
        if document_text:
            document_section = (
                "\nSUPPLEMENTARY DOCUMENTS (investment memos, diligence docs, etc.):\n"
                f"{document_text[:MAX_CHARS_COMBINED]}\n"
            )
        profile_prompt = PROFILE_PROMPT_TEMPLATE.format(
            url=actual_url,
            content=scraped_text[:12000],
            document_section=document_section,
        )

        # Build risk prompt (from raw text, not profile)
        risk_prompt = _build_risk_prompt_from_text(scraped_text, actual_url, document_text)

        timer = StepTimer("ParallelProfileAndRisk")

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_profile = pool.submit(
                self._run_ai_call,
                profile_prompt,
                PROFILE_SCHEMA,
                PROFILE_SYSTEM_PROMPT,
                "extract_profile",
            )
            future_risk = pool.submit(
                self._run_ai_call,
                risk_prompt,
                RISK_SCHEMA,
                RISK_SYSTEM_PROMPT,
                "assess_risk",
            )

            results: dict[str, tuple[dict[str, Any], float]] = {}
            for future in as_completed([future_profile, future_risk]):
                label, data, elapsed = future.result()
                results[label] = (data, elapsed)

        profile_data, profile_elapsed = results["extract_profile"]
        risk_data, risk_elapsed = results["assess_risk"]

        timer.record("ai_call_extract_profile", profile_elapsed)
        timer.record("ai_call_assess_risk", risk_elapsed)

        # Build and validate profile
        profile = CompanyProfile(**profile_data)
        if not profile.company_name or not profile.industry:
            message = (
                "Profile extraction returned incomplete data — company_name or industry missing"
            )
            raise ValueError(message)
        accessor.set_profile(profile)

        # Build and validate risk assessment
        risk_scores = [RiskScore(**rs) for rs in risk_data["risk_scores"]]
        if not risk_scores:
            message = "Risk assessment returned no risk scores"
            raise ValueError(message)
        assessment = RiskAssessment(
            risk_scores=risk_scores,
            overall_score=risk_data["overall_score"],
            tier=risk_data["tier"],
            top_risks=risk_data["top_risks"],
            analysis_summary=risk_data["analysis_summary"],
        )
        accessor.set_risk_assessment(assessment)

        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("extract_profile")
        self.request_executor.mark_question_complete("assess_risk")

    def _run_ai_call(
        self,
        user_prompt: str,
        schema: dict[str, Any],
        system_prompt: str,
        label: str,
    ) -> tuple[str, dict[str, Any], float]:
        """Execute a single AI call and return (label, response_data, elapsed_seconds)."""
        client = self._ai_client_factory.get_client(
            verbosity=Verbosity.MEDIUM,
            reasoning_effort=ReasoningEffort.LOW,
            precision=Precision.STANDARD,
            instructions=system_prompt,
        )
        logger.info(
            "[ParallelProfileAndRisk:%s] sending AI request: prompt_len=%d, model=%s",
            label,
            len(user_prompt),
            getattr(client, "model", "unknown"),
        )
        start = time.monotonic()
        try:
            response = client.query_structured(input_text=user_prompt, json_schema=schema)
        except Exception:
            logger.exception("[ParallelProfileAndRisk:%s] AI request failed", label)
            raise
        elapsed = time.monotonic() - start
        logger.info(
            "[ParallelProfileAndRisk:%s] AI response received in %.2fs: metadata=%s",
            label,
            elapsed,
            response.metadata,
        )
        return label, response.content, elapsed
