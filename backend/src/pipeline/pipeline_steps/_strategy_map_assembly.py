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
    ``strategicPriorities`` and ``arrows``. A legacy monolithic Step 7
    call may also produce a ``whatsMissing`` block — it is silently
    dropped here (the field was removed from the assembled output as
    part of the ``redesign-strategy-map`` Phase 2 change).
    """
    return StrategyMap(
        vision=VisionStatement(**vision),
        mission=MissionStatement(**mission),
        valueProposition=ValuePropositionClassification(**value_proposition),
        strategicPriorities=[StrategicPriority(**sp) for sp in finale["strategicPriorities"]],
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
                    objectives=[InternalProcessObjective(**o) for o in theme["objectives"]],
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


# ── Positional ID assignment ─────────────────────────────────────────────────
#
# Per-call schemas under `prompts/strategy_map/schemas/per_call/` omit
# the `id` field — parallel calls cannot reliably know their position in
# the title list. The assembly layer assigns IDs deterministically from
# the title-list order returned by Round 1.


def build_financial_objectives(
    titles: list[str],
    details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine Round 1 titles with Round 2 details into FinancialObjective dicts.

    IDs are assigned positionally as F1/F2/F3 from the title list order.
    Lists must be the same length; Pydantic validation downstream catches
    length-mismatch errors with a clearer message than this helper would.
    """
    _check_same_length(titles, details, "financial")
    return [
        {"id": f"F{index + 1}", "title": title, **detail}
        for index, (title, detail) in enumerate(zip(titles, details, strict=True))
    ]


def build_customer_objectives(
    titles: list[str],
    details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine Round 1 titles with Round 2 details into CustomerObjective dicts.

    IDs are assigned positionally as C1..C4 from the title list order.
    """
    _check_same_length(titles, details, "customer")
    return [
        {"id": f"C{index + 1}", "title": title, **detail}
        for index, (title, detail) in enumerate(zip(titles, details, strict=True))
    ]


def build_internal_themes(
    themes_meta: list[dict[str, Any]],
    titles_per_theme: list[list[str]],
    details_per_theme: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    r"""Assemble the internal-processes themes from the three-round outputs.

    - ``themes_meta`` is Round 1's output: list of
      ``{name, supports_financial_objectives}``.
    - ``titles_per_theme[i]`` is Round 2's output for theme ``i``: list of
      objective titles.
    - ``details_per_theme[i][j]`` is Round 3's output for theme ``i`` /
      objective ``j``: ``{definition, category, confidence, rationale_source}``.

    IDs are assigned as ``I{theme_idx + 1}.{obj_idx + 1}`` (1-indexed for both,
    matching the existing ``^I[1-3]\.[1-9]$`` regex constraint).
    """
    if not (len(themes_meta) == len(titles_per_theme) == len(details_per_theme)):
        message = (
            f"Internal-processes assembly mismatch: themes_meta={len(themes_meta)}, "
            f"titles_per_theme={len(titles_per_theme)}, "
            f"details_per_theme={len(details_per_theme)}"
        )
        raise ValueError(message)

    themes: list[dict[str, Any]] = []
    for theme_index, (theme, titles, details) in enumerate(
        zip(themes_meta, titles_per_theme, details_per_theme, strict=True)
    ):
        _check_same_length(titles, details, f"internal theme {theme_index + 1}")
        objectives = [
            {
                "id": f"I{theme_index + 1}.{obj_index + 1}",
                "title": title,
                **detail,
            }
            for obj_index, (title, detail) in enumerate(zip(titles, details, strict=True))
        ]
        themes.append(
            {
                "name": theme["name"],
                "supports_financial_objectives": theme["supports_financial_objectives"],
                "objectives": objectives,
            }
        )
    return themes


def build_capacity_objectives(
    titles: dict[str, str],
    details: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Combine Round 1 capacity titles with Round 2 details into the capacity dict.

    Capacity is bucket-keyed (people / technology / culture) — IDs are fixed
    (O.P / O.T / O.C). Both ``titles`` and ``details`` are dicts keyed by
    bucket; this returns the assembled ``{people, technology, culture}``
    structure expected by ``assemble_strategy_map``.
    """
    expected_buckets = {"people", "technology", "culture"}
    if set(titles.keys()) != expected_buckets:
        message = (
            f"Capacity titles missing required buckets: got {sorted(titles.keys())}, "
            f"need {sorted(expected_buckets)}"
        )
        raise ValueError(message)
    if set(details.keys()) != expected_buckets:
        message = (
            f"Capacity details missing required buckets: got {sorted(details.keys())}, "
            f"need {sorted(expected_buckets)}"
        )
        raise ValueError(message)
    bucket_to_id = {"people": "O.P", "technology": "O.T", "culture": "O.C"}
    return {
        bucket: {
            "id": bucket_to_id[bucket],
            "title": titles[bucket],
            **details[bucket],
        }
        for bucket in expected_buckets
    }


def _check_same_length(
    titles: list[Any],
    details: list[Any],
    perspective: str,
) -> None:
    """Internal helper: titles and details lists must be the same length.

    Length mismatch indicates an orchestration bug (a Round 2 call
    failed silently or a parallel result was dropped). Fail loudly so
    the failure surfaces in CloudWatch rather than producing a strategy
    map with N titles but N-1 details.
    """
    if len(titles) != len(details):
        message = (
            f"{perspective} assembly: titles={len(titles)} but "
            f"details={len(details)}; lists must match in length"
        )
        raise ValueError(message)
