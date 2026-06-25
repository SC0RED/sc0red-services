"""Composite step: runs profile, risk, and ideation AI calls in parallel.

Runs 11 AI calls concurrently at Level 1:
  - 1 profile extraction
  - 2 risk assessment batches (4 categories each)
  - 8 opportunity ideation calls (one per risk category)

After all complete, risk aggregates are computed programmatically and ideations
are deduplicated, ranked, and stored for the detail phase.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from signalfield_core.models.enums import Precision
from signalfield_core.pipeline.step import RequestStep
from signalfield_core.utilities.future_manager import FutureManager

from src.documents.extract_text import MAX_CHARS_COMBINED, MAX_SCRAPED_TEXT_CHARS
from src.models.model_company import CompanyProfile, RiskAssessment, RiskScore
from src.pipeline.ai_guides.ideation_guide import IDEATION_GUIDE
from src.pipeline.ai_guides.risk_scoring_guide import RISK_SCORING_GUIDE
from src.pipeline.company_name import resolve_company_name
from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call
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
from src.pipeline.pipeline_steps.ideate_opportunities import (
    IDEATION_SCHEMA,
    IDEATION_SYSTEM_PROMPT,
    build_ideation_prompt,
    get_all_ideation_categories,
)
from src.pipeline.pipeline_steps.rank_opportunities import (
    deduplicate_ideations,
    derive_top_three_actions,
    filter_low_quality_ideations,
    rank_ideations,
)
from src.pipeline.prompts.loader import load_template
from src.pipeline.step_timer import StepTimer

if TYPE_CHECKING:
    from signalfield_core.services.ai_client_factory import AIClientFactory

    from src.facades.company_accessor import CompanyAccessor
    from src.pipeline.pipeline_steps.ai_call import TokenCounts

logger = logging.getLogger(__name__)


_RISK_BATCH_TEMPLATE = load_template("risk_batch")


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

    return _RISK_BATCH_TEMPLATE.format(
        url=url,
        scraped_text=scraped_text[:MAX_SCRAPED_TEXT_CHARS],
        document_section=document_section,
        categories_block=categories_block,
        risk_industry_weighting=RISK_INDUSTRY_WEIGHTING,
        risk_assessment_questions=RISK_ASSESSMENT_QUESTIONS,
        num_categories=len(categories),
    )


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


class ParallelProfileRiskAndIdeation(RequestStep):
    """Runs profile, risk, and ideation AI calls in parallel.

    Runs 11 AI calls concurrently: 1 profile extraction + 2 risk assessment
    batches (4 categories each) + 8 ideation calls (one per risk category).
    Risk aggregates and ideation ranking are computed programmatically.
    """

    def __init__(self, ai_client_factory: AIClientFactory | None = None) -> None:
        super().__init__()
        self._ai_client_factory = ai_client_factory

    def execute(self) -> None:
        """Run profile extraction, risk assessment, and ideation in parallel."""
        accessor = cast("CompanyAccessor", self.entity_accessor)
        scraped_text = accessor.get_scraped_text()
        actual_url = accessor.company.actual_url or accessor.company.url
        document_text = accessor.get_document_text()

        if not self._ai_client_factory:
            message = "AI client factory not configured"
            raise RuntimeError(message)

        # Build profile prompt
        document_section = ""
        if document_text:
            document_section = (
                "\nSUPPLEMENTARY DOCUMENTS (investment memos, diligence docs, etc.):\n"
                f"{document_text[:MAX_CHARS_COMBINED]}\n"
            )
        profile_prompt = PROFILE_PROMPT_TEMPLATE.format(
            url=actual_url,
            content=scraped_text[:MAX_SCRAPED_TEXT_CHARS],
            document_section=document_section,
        )

        # Build risk batch prompts
        risk_batch_a_prompt = _build_risk_batch_prompt(
            scraped_text, actual_url, RISK_BATCH_A_CATEGORIES, document_text
        )
        risk_batch_b_prompt = _build_risk_batch_prompt(
            scraped_text, actual_url, RISK_BATCH_B_CATEGORIES, document_text
        )

        # Build 8 ideation prompts (one per risk category)
        ideation_categories = get_all_ideation_categories()
        ideation_prompts: list[tuple[str, str]] = []  # (label, prompt)
        for category in ideation_categories:
            prompt = build_ideation_prompt(
                scraped_text=scraped_text,
                url=actual_url,
                category_id=category["id"],
                category_name=category["name"],
                category_description=category["description"],
                document_text=document_text,
            )
            ideation_prompts.append((f"ideation_{category['id']}", prompt))

        timer = StepTimer("ParallelProfileRiskAndIdeation")

        # Run all 11 AI calls in parallel
        with FutureManager(name="ParallelProfileRiskAndIdeation", max_workers=11) as manager:
            # ``extract_profile`` runs on Precision.ADVANCED (gpt-5.1).
            # The sc0red Services 2026-05-15 benchmark flagged mini for misclassifying
            # ``industry_sector`` as "Manufacturing" (should be Technology)
            # and dropping anchor numbers in ``revenue_model`` /
            # ``competitive_positioning``. Other calls below use the default
            # STANDARD (gpt-5.4-mini).
            manager.submit_task(
                self._run_ai_call,
                profile_prompt,
                PROFILE_SCHEMA,
                PROFILE_SYSTEM_PROMPT,
                "extract_profile",
                Precision.ADVANCED,
            )
            risk_instructions = RISK_SYSTEM_PROMPT + "\n\n" + RISK_SCORING_GUIDE
            manager.submit_task(
                self._run_ai_call,
                risk_batch_a_prompt,
                RISK_BATCH_SCHEMA,
                risk_instructions,
                "assess_risk_batch_a",
            )
            manager.submit_task(
                self._run_ai_call,
                risk_batch_b_prompt,
                RISK_BATCH_SCHEMA,
                risk_instructions,
                "assess_risk_batch_b",
            )
            ideation_instructions = IDEATION_SYSTEM_PROMPT + "\n\n" + IDEATION_GUIDE
            for label, prompt in ideation_prompts:
                manager.submit_task(
                    self._run_ai_call,
                    prompt,
                    IDEATION_SCHEMA,
                    ideation_instructions,
                    label,
                )
            all_results = manager.wait_for_all_and_collect_results()

        # Drop the per-call ``TokenCounts`` (4th tuple element from
        # run_structured_ai_call as of 2026-05-15) — this step doesn't surface
        # token telemetry yet. Opt-in by calling timer.record_tokens(...)
        # below if/when that becomes desired.
        results: dict[str, tuple[dict[str, Any], float]] = {}
        for label, data, elapsed, _tokens in all_results:
            results[label] = (data, elapsed)

        profile_data, profile_elapsed = results["extract_profile"]
        risk_batch_a_data, risk_batch_a_elapsed = results["assess_risk_batch_a"]
        risk_batch_b_data, risk_batch_b_elapsed = results["assess_risk_batch_b"]

        timer.record("ai_call_extract_profile", profile_elapsed)
        timer.record("ai_call_assess_risk_batch_a", risk_batch_a_elapsed)
        timer.record("ai_call_assess_risk_batch_b", risk_batch_b_elapsed)

        # Build and validate profile
        profile = CompanyProfile(**profile_data)
        if not profile.industry:
            message = "Profile extraction returned incomplete data — industry missing"
            raise ValueError(message)
        # ``company_name`` is an identity label, not a grounded fact: extraction
        # occasionally returns blank/"unknown" when the name lives in stripped
        # markup. Normalise it once here (seed name → domain) so every
        # downstream step — financials, EBITDA tree, value chain, strategy map,
        # and persistence — uses the clean name rather than the literal
        # "unknown" (the millerenv.com regression).
        profile.company_name = resolve_company_name(
            profile.company_name,
            accessor.company.company_name,
            actual_url,
        )
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

        # Build risk score lookup for ranking
        risk_score_lookup: dict[str, float] = {
            score.category: score.score for score in all_risk_scores
        }

        # Collect and process ideation results (copy dicts to avoid mutating AI response)
        raw_ideations: list[dict[str, Any]] = []
        for category in ideation_categories:
            label = f"ideation_{category['id']}"
            ideation_data, ideation_elapsed = results[label]
            timer.record(f"ai_call_{label}", ideation_elapsed)
            raw_ideations.append({**ideation_data, "risk_category": category["id"]})

        # Filter low-quality, deduplicate, rank, and derive top actions
        filtered = filter_low_quality_ideations(raw_ideations, risk_score_lookup)
        deduped = deduplicate_ideations(filtered, risk_score_lookup)
        ranked = rank_ideations(deduped, risk_score_lookup)
        top_actions = derive_top_three_actions(ranked)

        # Store ranked ideations with top actions for the detail phase
        ranked_with_actions = [
            {**ideation, "top_three_immediate_actions": top_actions} for ideation in ranked
        ]
        accessor.set_ranked_ideations(ranked_with_actions)

        self.request_executor.add_details(timer.to_details())
        self.request_executor.mark_question_complete("extract_profile")
        self.request_executor.mark_question_complete("assess_risk")
        self.request_executor.mark_question_complete("ideate_opportunities")

    def _run_ai_call(
        self,
        user_prompt: str,
        schema: dict[str, Any],
        system_prompt: str,
        label: str,
        precision: Precision = Precision.STANDARD,
    ) -> tuple[str, dict[str, Any], float, TokenCounts]:
        """Execute a single AI call via the shared run_structured_ai_call.

        ``precision`` defaults to ``STANDARD`` (gpt-5.4-mini). The
        ``extract_profile`` call passes ``Precision.ADVANCED`` (gpt-5.1)
        because the sc0red Services 2026-05-15 benchmark flagged mini for misclassifying
        ``industry_sector`` and dropping anchor numbers in ``revenue_model`` /
        ``competitive_positioning``. Risk-batch and ideation calls accept
        mini-quality outputs per the same benchmark.
        """
        return run_structured_ai_call(
            ai_client_factory=self._ai_client_factory,
            user_prompt=user_prompt,
            schema=schema,
            system_prompt=system_prompt,
            label=label,
            step_name="ParallelProfileRiskAndIdeation",
            precision=precision,
        )
