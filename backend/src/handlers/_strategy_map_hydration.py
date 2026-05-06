"""Hydrate a ``Company`` Pydantic model from persisted DynamoDB records.

The strategy-map on-demand worker (``strategy_map_handler``) needs the same
in-memory Company shape that the analysis pipeline produces, but loaded from
the persistence layer rather than computed by upstream pipeline steps. This
module owns the dict-to-Pydantic conversion for that path.

Lives in its own module so the worker stays focused on orchestration, and so
the conversion can be unit-tested without standing up the full pipeline.

Shape note: the assessment-repository getters return mixed shapes —
``get_risk_scores``/``get_opportunities`` return DynamoDB-row dicts
(snake_case, mostly aligned with Pydantic field names); ``get_ebitda_tree``/
``get_value_chain`` return camelCase API-shape dicts that
``analysis_payload`` ships to the frontend directly. Hydration here unifies
both into snake_case Pydantic models so ``GenerateStrategyMap`` sees the
exact shape the pipeline-step path produces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.models.model_company import (
    Company,
    CompanyProfile,
    EbitdaNode,
    EbitdaTreeResult,
    Opportunity,
    OpportunityResult,
    RiskAssessment,
    RiskScore,
    ValueChainResult,
    ValueChainStep,
)

if TYPE_CHECKING:
    from src.repositories.dynamodb.provider import DynamoDBStorageProvider


class StrategyMapHydrationError(ValueError):
    """Raised when the analysis is missing prerequisite data needed to generate a strategy map.

    Used by the worker to translate a structural absence (e.g., the analysis
    has no risk assessment yet) into a recoverable failure mode — the user
    sees a "We couldn't generate your strategy map" message; the underlying
    cause is logged to CloudWatch.
    """


def hydrate_company_for_strategy_map(
    storage: DynamoDBStorageProvider,
    analysis_id: str,
) -> Company:
    """Load and hydrate a ``Company`` model with everything strategy-map generation needs.

    Reads the company record + its latest assessment + all sub-records, then
    constructs a fully-populated ``Company`` Pydantic model that
    ``GenerateStrategyMap`` can consume identically to the in-pipeline path.

    Raises:
        StrategyMapHydrationError: when the company or assessment is missing,
            or when the assessment lacks the prerequisite data
            (profile / risk assessment / opportunities) the strategy-map step
            requires. The strategy-map step itself raises the same shape of
            errors when called from the pipeline; centralising the load here
            keeps the failure path consistent.
    """
    company_repo = storage.create_company_repository()
    assessment_repo = storage.create_assessment_repository()

    company_record = company_repo.get_by_id(analysis_id)
    if company_record is None:
        message = f"Cannot hydrate company: analysis {analysis_id} not found"
        raise StrategyMapHydrationError(message)

    assessments = assessment_repo.find_by_company(analysis_id)
    if not assessments:
        message = f"Cannot hydrate company: analysis {analysis_id} has no assessment record"
        raise StrategyMapHydrationError(message)

    # Mirror analysis_payload's "newest assessment wins" rule for re-analyse races.
    assessments.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    assessment = assessments[0]
    assessment_id = assessment["id"]

    profile = _hydrate_profile(company_record, assessment)
    risk_assessment = _hydrate_risk_assessment(
        company_record, assessment_repo.get_risk_scores(assessment_id)
    )
    opportunity_result = _hydrate_opportunity_result(
        assessment_repo.get_opportunities(assessment_id)
    )
    ebitda_tree = _hydrate_ebitda_tree(assessment_repo.get_ebitda_tree(assessment_id))
    value_chain = _hydrate_value_chain(assessment_repo.get_value_chain(assessment_id))

    return Company(
        id=analysis_id,
        scan_id=company_record.get("scan_id", ""),
        org_id=company_record.get("org_id", ""),
        user_id=company_record.get("created_by", ""),
        company_name=company_record.get("company_name", ""),
        url=company_record.get("company_url", ""),
        profile=profile,
        risk_assessment=risk_assessment,
        opportunity_result=opportunity_result,
        ebitda_tree=ebitda_tree,
        value_chain=value_chain,
    )


def _hydrate_profile(
    company_record: dict[str, Any], assessment: dict[str, Any]
) -> CompanyProfile | None:
    """Construct a ``CompanyProfile`` from the company + assessment metadata.

    The profile shape is split across the two records: company-level fields
    (name, industry, business model, size) live on the company record;
    free-text descriptors (description, products, target market) live on
    assessment metadata if they were captured. The pipeline-step path sees a
    Pydantic-validated profile assembled by ``ExtractProfile``; hydration
    reconstructs the same shape from persistence.
    """
    company_name = company_record.get("company_name", "")
    industry = company_record.get("industry", "")
    if not company_name or not industry:
        # Profile is required. Strategy-map generation has its own validity gate
        # (raises ValueError when profile is missing); raise here so the failure
        # surfaces with hydration context rather than as a downstream KeyError.
        return None

    return CompanyProfile(
        company_name=company_name,
        industry=industry,
        industry_sector=company_record.get("industry_sector", ""),
        business_model=company_record.get("business_model", ""),
        description=assessment.get("company_description", ""),
        products_services=assessment.get("products_services", []),
        target_market=company_record.get("target_market", ""),
        company_size=company_record.get("company_size", ""),
        revenue_model=company_record.get("revenue_model", ""),
        tech_signals=assessment.get("tech_signals", []),
        competitive_positioning=assessment.get("competitive_positioning", ""),
        ai_maturity=company_record.get("ai_maturity", ""),
        key_risks_visible=assessment.get("key_risks_visible", []),
    )


def _hydrate_risk_assessment(
    company_record: dict[str, Any], risk_score_records: list[dict[str, Any]]
) -> RiskAssessment | None:
    """Construct a ``RiskAssessment`` from the company-level overall + per-category rows.

    Returns ``None`` when there are no persisted risk scores — the caller
    converts that into a hydration error before invoking the strategy-map
    step (which itself fails fast on missing risk data).
    """
    if not risk_score_records:
        return None

    risk_scores = [
        RiskScore(
            category=item["category"],
            score=float(item["score"]),
            rationale=item.get("rationale", ""),
        )
        for item in risk_score_records
    ]
    return RiskAssessment(
        risk_scores=risk_scores,
        overall_score=float(company_record.get("overall_risk_score") or 0.0),
        tier=company_record.get("risk_tier") or "low",
    )


def _hydrate_opportunity_result(
    opportunity_records: list[dict[str, Any]],
) -> OpportunityResult | None:
    """Construct an ``OpportunityResult`` from the per-opportunity rows.

    Maps the persisted shape (one DynamoDB row per opportunity, with
    ``implementation_steps`` already JSON-decoded by the repository getter)
    to the Pydantic ``Opportunity`` shape.
    """
    if not opportunity_records:
        return None

    opportunities = [
        Opportunity(
            title=item.get("title", ""),
            impact_rating=item.get("impact_rating", ""),
            strategic_category=item.get("strategic_category", ""),
            description=item.get("description", ""),
            implementation_steps=item.get("implementation_steps", []) or [],
            timeline=item.get("timeline", ""),
            investment_range=item.get("investment_range", ""),
            roi_estimate=item.get("roi_estimate", ""),
            value_lever=item.get("value_lever") or None,
        )
        for item in opportunity_records
    ]
    return OpportunityResult(opportunities=opportunities)


def _hydrate_ebitda_tree(
    ebitda_tree_record: dict[str, Any] | None,
) -> EbitdaTreeResult | None:
    """Convert the camelCase API-shape EBITDA tree dict back into Pydantic.

    ``assessment_repo.get_ebitda_tree`` returns camelCase keys so it can pass
    through ``analysis_payload`` to the frontend unchanged. Hydration reverses
    that for the worker's consumption.
    """
    if not ebitda_tree_record:
        return None

    nodes = [_hydrate_ebitda_node(node) for node in ebitda_tree_record.get("treeData", [])]
    return EbitdaTreeResult(
        summary=ebitda_tree_record.get("businessModelSummary", ""),
        revenue_estimate=ebitda_tree_record.get("revenueEstimate", ""),
        ebitda_estimate=ebitda_tree_record.get("ebitdaEstimate", ""),
        nodes=nodes,
    )


def _hydrate_ebitda_node(node_dict: dict[str, Any]) -> EbitdaNode:
    """Recursively build an ``EbitdaNode`` from a persisted dict."""
    children = [_hydrate_ebitda_node(child) for child in node_dict.get("children", [])]
    return EbitdaNode(
        id=node_dict["id"],
        label=node_dict["label"],
        type=node_dict["type"],
        value_range=node_dict.get("value_range"),
        percentage_of_parent=node_dict.get("percentage_of_parent"),
        description=node_dict.get("description", ""),
        linked_opportunity_indices=node_dict.get("linked_opportunity_indices", []),
        children=children,
        confidence_level=node_dict.get("confidence_level"),
        confidence_basis=node_dict.get("confidence_basis"),
    )


def _hydrate_value_chain(
    value_chain_record: dict[str, Any] | None,
) -> ValueChainResult | None:
    """Convert a persisted value-chain dict into Pydantic.

    The repository getter returns the camelCase shape ``{steps: [...], summary: str}``;
    each step's fields are already snake_case-aligned because Pydantic validation
    runs at write time.
    """
    if not value_chain_record:
        return None

    steps = [
        ValueChainStep(
            id=step.get("id", ""),
            label=step.get("label", step.get("name", "")),
            description=step.get("description", ""),
            category=step.get("category", "primary"),
            risk_categories=step.get("risk_categories", []),
            opportunity_indices=step.get("opportunity_indices", []),
        )
        for step in value_chain_record.get("steps", [])
    ]
    return ValueChainResult(
        summary=value_chain_record.get("summary", ""),
        steps=steps,
    )
