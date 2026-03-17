"""Composite step: runs profile extraction and risk assessment AI calls in parallel.

Instead of the sequential ExtractProfile → AssessRisk flow, this step makes 3
AI calls concurrently: 1 profile extraction + 2 risk assessment batches (4
categories each). The risk batches are split by thematic relevance — external
market threats vs internal/operational risks — preserving cross-category
reasoning within each batch. Aggregate fields (overall_score, tier, top_risks,
analysis_summary) are computed programmatically after both batches complete.

Saves ~30-45s of wall-clock time by overlapping all three calls, and the 2x4
risk split further reduces the risk assessment from ~49s to ~25-30s.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.models.enums import Precision, ReasoningEffort, Verbosity
from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManager

from src.documents.extract_text import MAX_CHARS_COMBINED
from src.models.model_company import CompanyProfile, RiskAssessment, RiskScore
from src.pipeline.pipeline_steps.assess_risk import (
    RISK_ASSESSMENT_QUESTIONS,
    RISK_BATCH_A_CATEGORIES,
    RISK_BATCH_B_CATEGORIES,
    RISK_BATCH_SCHEMA,
    RISK_INDUSTRY_WEIGHTING,
    RISK_SYSTEM_PROMPT,
    build_risk_batch_categories_block,
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


def _build_risk_batch_prompt(
    scraped_text: str,
    url: str,
    categories: list[str],
    document_text: str | None = None,
) -> str:
    """Build risk assessment prompt for a batch of 4 categories."""
    document_section = ""
    if document_text:
        document_section = f"\n\nSUPPLEMENTARY DOCUMENTS:\n{document_text[:MAX_CHARS_COMBINED]}"

    categories_block = build_risk_batch_categories_block(categories)

    return f"""Perform an AI disruption risk assessment for this company, \
focusing on the specific risk categories listed below.

COMPANY URL: {url}

WEBSITE CONTENT:
{scraped_text[:12000]}{document_section}

RISK CATEGORIES TO ASSESS:
{categories_block}

INDUSTRY CONTEXT: Based on the company information above, apply industry-specific weighting:
{RISK_INDUSTRY_WEIGHTING}

{RISK_ASSESSMENT_QUESTIONS}

IMPORTANT: Assess ONLY the {len(categories)} risk categories listed above. \
Score them relative to each other — use the full 1-10 scale, not just the middle range."""


_TIER_CRITICAL_THRESHOLD = 8.5
_TIER_HIGH_THRESHOLD = 6.5
_TIER_MODERATE_THRESHOLD = 3.5


def compute_risk_aggregates(
    risk_scores: list[RiskScore],
    company_name: str,
) -> RiskAssessment:
    """Compute overall_score, tier, top_risks, and analysis_summary from risk scores.

    This replaces the AI-generated aggregates with deterministic programmatic computation,
    ensuring consistency when risk scores come from two separate batch calls.
    """
    if not risk_scores:
        message = "Cannot compute risk aggregates from empty risk_scores list"
        raise ValueError(message)

    overall_score = round(sum(score.score for score in risk_scores) / len(risk_scores), 1)

    if overall_score >= _TIER_CRITICAL_THRESHOLD:
        tier = "critical"
    elif overall_score >= _TIER_HIGH_THRESHOLD:
        tier = "high"
    elif overall_score >= _TIER_MODERATE_THRESHOLD:
        tier = "moderate"
    else:
        tier = "low"

    sorted_scores = sorted(risk_scores, key=lambda s: s.score, reverse=True)
    top_risks = [score.category for score in sorted_scores[:3]]

    top_three = sorted_scores[:3]
    risk_details = ", ".join(f"{s.category} ({s.score}/10)" for s in top_three)
    analysis_summary = (
        f"{company_name} faces {tier} AI disruption risk "
        f"(overall: {overall_score}/10). "
        f"Highest risk areas: {risk_details}."
    )

    return RiskAssessment(
        risk_scores=risk_scores,
        overall_score=overall_score,
        tier=tier,
        top_risks=top_risks,
        analysis_summary=analysis_summary,
    )


class ParallelProfileAndRisk(RequestStep):
    """Runs profile extraction and risk assessment AI calls in parallel.

    Replaces the sequential ExtractProfile → AssessRisk pair in the pipeline.
    Runs 3 AI calls concurrently: 1 profile extraction + 2 risk assessment batches
    (4 categories each, split by thematic relevance). Risk aggregates are computed
    programmatically after both batches complete.
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

        # Build risk batch prompts (2 batches of 4 categories each)
        risk_batch_a_prompt = _build_risk_batch_prompt(
            scraped_text, actual_url, RISK_BATCH_A_CATEGORIES, document_text
        )
        risk_batch_b_prompt = _build_risk_batch_prompt(
            scraped_text, actual_url, RISK_BATCH_B_CATEGORIES, document_text
        )

        timer = StepTimer("ParallelProfileAndRisk")

        with FutureManager(name="ParallelProfileAndRisk", max_workers=3) as manager:
            manager.submit_task(
                self._run_ai_call,
                profile_prompt,
                PROFILE_SCHEMA,
                PROFILE_SYSTEM_PROMPT,
                "extract_profile",
            )
            manager.submit_task(
                self._run_ai_call,
                risk_batch_a_prompt,
                RISK_BATCH_SCHEMA,
                RISK_SYSTEM_PROMPT,
                "assess_risk_batch_a",
            )
            manager.submit_task(
                self._run_ai_call,
                risk_batch_b_prompt,
                RISK_BATCH_SCHEMA,
                RISK_SYSTEM_PROMPT,
                "assess_risk_batch_b",
            )
            all_results = manager.wait_for_all_and_collect_results()

        results: dict[str, tuple[dict[str, Any], float]] = {}
        for label, data, elapsed in all_results:
            results[label] = (data, elapsed)

        profile_data, profile_elapsed = results["extract_profile"]
        risk_batch_a_data, risk_batch_a_elapsed = results["assess_risk_batch_a"]
        risk_batch_b_data, risk_batch_b_elapsed = results["assess_risk_batch_b"]

        timer.record("ai_call_extract_profile", profile_elapsed)
        timer.record("ai_call_assess_risk_batch_a", risk_batch_a_elapsed)
        timer.record("ai_call_assess_risk_batch_b", risk_batch_b_elapsed)

        # Build and validate profile
        profile = CompanyProfile(**profile_data)
        if not profile.company_name or not profile.industry:
            message = (
                "Profile extraction returned incomplete data — company_name or industry missing"
            )
            raise ValueError(message)
        accessor.set_profile(profile)

        # Merge risk scores from both batches, deduplicating by category
        seen_categories: set[str] = set()
        all_risk_scores: list[RiskScore] = []
        for rs in risk_batch_a_data["risk_scores"] + risk_batch_b_data["risk_scores"]:
            if rs["category"] not in seen_categories:
                seen_categories.add(rs["category"])
                all_risk_scores.append(RiskScore(**rs))
        if not all_risk_scores:
            message = "Risk assessment returned no risk scores"
            raise ValueError(message)

        # Compute aggregates programmatically
        assessment = compute_risk_aggregates(all_risk_scores, profile.company_name)
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
