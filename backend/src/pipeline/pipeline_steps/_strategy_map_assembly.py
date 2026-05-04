"""Strategy map output assembly + Pydantic validation.

Extracted from `generate_strategy_map.py` to keep that file under the
400-line limit. Responsible for converting the seven-step generation
outputs into a validated `StrategyMap` instance.

Pydantic does the schema validation. If anything is shaped wrong,
the constructor raises a `ValidationError` and the pipeline error
path surfaces it (per CLAUDE.md fail-fast: do not swallow exceptions).
"""

from __future__ import annotations

from typing import Any

from src.models.model_strategy_map import (
    Arrow,
    CapacityObjective,
    CoreValues,
    CustomerObjective,
    CustomerPerspective,
    FinancialObjective,
    FinancialPerspective,
    Gap,
    InternalProcessesPerspective,
    InternalProcessObjective,
    InternalProcessTheme,
    MissionStatement,
    OrganizationalCapacityPerspective,
    StrategicPriority,
    StrategyMap,
    ValuePropositionClassification,
    VisionStatement,
)


def assemble_strategy_map(
    *,
    vision: dict[str, Any],
    mission: dict[str, Any],
    value_proposition: dict[str, Any],
    financial: dict[str, Any],
    customer: dict[str, Any],
    internal_processes: dict[str, Any],
    organizational_capacity: dict[str, Any],
    core_values: dict[str, Any],
    finale: dict[str, Any],
) -> StrategyMap:
    """Build a validated StrategyMap from the seven-step outputs.

    The `finale` dict carries the Step 7 output, which contains
    `strategicPriorities`, `arrows`, and `whatsMissing`.
    """
    return StrategyMap(
        vision=VisionStatement(**vision),
        mission=MissionStatement(**mission),
        valueProposition=ValuePropositionClassification(**value_proposition),
        strategicPriorities=[
            StrategicPriority(**sp) for sp in finale["strategicPriorities"]
        ],
        financial=FinancialPerspective(
            objectives=[FinancialObjective(**o) for o in financial["objectives"]]
        ),
        customer=CustomerPerspective(
            objectives=[CustomerObjective(**o) for o in customer["objectives"]]
        ),
        internalProcesses=InternalProcessesPerspective(
            themes=[
                InternalProcessTheme(
                    name=theme["name"],
                    supports_financial_objectives=theme["supports_financial_objectives"],
                    objectives=[
                        InternalProcessObjective(**o) for o in theme["objectives"]
                    ],
                )
                for theme in internal_processes["themes"]
            ]
        ),
        organizationalCapacity=OrganizationalCapacityPerspective(
            people=CapacityObjective(**organizational_capacity["people"]),
            technology=CapacityObjective(**organizational_capacity["technology"]),
            culture=CapacityObjective(**organizational_capacity["culture"]),
        ),
        arrows=[Arrow(**a) for a in finale["arrows"]],
        whatsMissing=[Gap(**g) for g in finale["whatsMissing"]],
        coreValues=CoreValues(**core_values),
    )


def extract_core_values(capacity_response: dict[str, Any]) -> dict[str, Any]:
    """Step 6 returns coreValues alongside the capacity perspective; pull it out.

    Raises ValueError if absent — Step 6 is required to produce the
    core-values block (the schema requires 3-6 values).
    """
    if "coreValues" in capacity_response:
        return capacity_response["coreValues"]
    message = (
        "GenerateStrategyMap: Step 6 response missing 'coreValues' — "
        "capacity step is required to produce them."
    )
    raise ValueError(message)
