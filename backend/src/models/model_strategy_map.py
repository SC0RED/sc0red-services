"""Pydantic models for the AI-generated Balanced Scorecard strategy map.

Mirrors the JSON schema at
`src/pipeline/prompts/strategy_map/schemas/strategy_map_output.json`.

The strategy map is an additive output of the company analysis
pipeline (see `pipeline/pipeline_steps/generate_strategy_map.py`),
positioned at the top of the analysis page in the rebranded Vector
Advisory product. It is high-level by design — public-data only, no
measures / targets / initiatives — to drive a "Contact us for deep
dive" conversion path.

Naming convention: snake_case internally; the API serialisation layer
in `handlers/analysis_payload.py` converts to camelCase for the
frontend.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ── Shared confidence marker ──────────────────────────────────────────────

ConfidenceMarker = Literal["HIGH", "MEDIUM", "LOW"]
"""Per-objective confidence in the AI's inference.

- HIGH   — directly inferred from concrete public data (e.g. financial
            objective derived from EBITDA tree numerics).
- MEDIUM — typical of similar companies in this industry; pattern-
            matched but not directly observed for this company.
- LOW    — inferred from absence; reasonable but unverified.
"""

# ── Vision and Mission ─────────────────────────────────────────────────────


class VisionStatement(BaseModel):
    """Vision statement for the strategy map's top band.

    Quoted at the top of the rendered map. Synthesised when no public
    vision exists — flagged so the renderer can show "(synthesised)".
    """

    statement: str = Field(min_length=10, max_length=200)
    synthesised: bool = False
    rationale: str = Field(min_length=10, max_length=300)


class MissionStatement(BaseModel):
    """Mission statement — current-tense purpose, plain language."""

    statement: str = Field(min_length=10, max_length=300)
    synthesised: bool = False
    rationale: str = Field(min_length=10, max_length=300)


# ── Customer Value Proposition (Treacy & Wiersema, 1995) ───────────────────

ValuePropositionEnum = Literal[
    "operational_excellence",
    "customer_intimacy",
    "product_leadership",
    "hybrid",
]


class ValuePropositionClassification(BaseModel):
    """Customer Value Proposition classification.

    Per K&N HBR 2000: companies excel at ONE proposition while
    maintaining threshold performance in the other two. `hybrid` is
    used when two propositions are clearly co-pursued (Mobil-style:
    customer intimacy + operational excellence). `secondary` is
    populated only when `primary == "hybrid"`.
    """

    primary: ValuePropositionEnum
    secondary: (
        Literal["operational_excellence", "customer_intimacy", "product_leadership"] | None
    ) = None
    rationale: str = Field(min_length=20, max_length=600)
    exemplar_company: str | None = Field(default=None, max_length=100)


# ── Strategic Priorities (matches Internal Process themes) ─────────────────


class StrategicPriority(BaseModel):
    """One strategic priority in the top header band.

    Strategic priorities map 1:1 to Internal Process themes — the
    same 2-3 named themes appear in both places.
    """

    name: str = Field(min_length=4, max_length=60)
    result: str = Field(min_length=20, max_length=300)


# ── Per-perspective objectives ─────────────────────────────────────────────


class FinancialObjective(BaseModel):
    """Financial perspective objective — revenue or productivity side."""

    id: str = Field(pattern=r"^F[123]$")
    title: str = Field(min_length=8, max_length=120)
    definition: str = Field(min_length=50, max_length=1200)
    category: Literal["revenue_growth", "productivity"]
    confidence: ConfidenceMarker
    rationale_source: str | None = Field(default=None, max_length=400)
    # ``linked_opportunity_indices`` — index pointers into the analysis's
    # ``opportunities`` array (same idiom as ``EbitdaNode.linked_opportunity_indices``
    # and ``ValueChainStep.opportunity_indices``). Surfaced by the frontend
    # as coloured dots on the BSC table cell — see the
    # ``redesign-analysis-visuals`` change (Phase 1a) and the
    # ``analysis-opportunity-overlays`` capability spec.
    #
    # Phase 1a ships only the data shape: legacy persisted records (which
    # never carried the field) deserialise to the empty-list default, and
    # the AI output JSON schema is unchanged (so the AI does not yet emit
    # the field — the pipeline does not populate it either). Phase 1b
    # adds the AI population layer.
    linked_opportunity_indices: list[int] = Field(default_factory=list[int])


class CustomerObjective(BaseModel):
    """Customer perspective objective — first-person customer voice.

    Vector house style: titles are first-person quotes from the
    customer's voice. The renderer adds the surrounding quotation
    marks; the JSON `title` value holds the inner text only.
    """

    id: str = Field(pattern=r"^C[1-4]$")
    title: str = Field(min_length=8, max_length=200)
    definition: str = Field(min_length=50, max_length=1200)
    panel: Literal["consumer", "channel", "partner"] = "consumer"
    confidence: ConfidenceMarker
    rationale_source: str | None = Field(default=None, max_length=400)
    # See ``FinancialObjective.linked_opportunity_indices`` for the
    # field's purpose and the Phase 1a/1b split.
    linked_opportunity_indices: list[int] = Field(default_factory=list[int])


class InternalProcessObjective(BaseModel):
    """Internal Processes objective — bucketed under a theme.

    The `id` follows the `I{theme_index}.{objective_index}` pattern
    (e.g. I1.1, I1.2, I2.1). Each objective is tagged with one of
    the four K&N internal-process categories.
    """

    id: str = Field(pattern=r"^I[1-3]\.[1-9]$")
    title: str = Field(min_length=8, max_length=200)
    definition: str = Field(min_length=50, max_length=1200)
    category: Literal[
        "innovation",
        "customer_management",
        "operational_excellence",
        "citizenship",
    ]
    confidence: ConfidenceMarker
    rationale_source: str | None = Field(default=None, max_length=400)
    # See ``FinancialObjective.linked_opportunity_indices`` for the
    # field's purpose and the Phase 1a/1b split.
    linked_opportunity_indices: list[int] = Field(default_factory=list[int])


class InternalProcessTheme(BaseModel):
    """A named theme grouping 1-4 internal-process objectives.

    Themes connect to revenue or productivity strategies in the
    Financial perspective via `supports_financial_objectives`. A theme
    that supports no financial objective is suspicious and should be
    surfaced as a gap.
    """

    name: str = Field(min_length=4, max_length=60)
    supports_financial_objectives: list[str] = Field(default_factory=list, min_length=1)
    objectives: list[InternalProcessObjective] = Field(min_length=1, max_length=4)


class CapacityObjective(BaseModel):
    """Organizational Capacity objective (one of People / Tech / Culture).

    The `id` is one of `O.P`, `O.T`, `O.C`. Vector v1 uses the
    People / Technology / Culture triad (renaming K&N's "Learning
    and Growth").
    """

    id: str = Field(pattern=r"^O\.[PTC]$")
    title: str = Field(min_length=8, max_length=200)
    definition: str = Field(min_length=50, max_length=1200)
    confidence: ConfidenceMarker
    rationale_source: str | None = Field(default=None, max_length=400)
    # See ``FinancialObjective.linked_opportunity_indices`` for the
    # field's purpose and the Phase 1a/1b split.
    linked_opportunity_indices: list[int] = Field(default_factory=list[int])


# ── Perspective containers ─────────────────────────────────────────────────


class FinancialPerspective(BaseModel):
    """Financial perspective — exactly 3 objectives."""

    objectives: list[FinancialObjective] = Field(min_length=3, max_length=3)


class CustomerPerspective(BaseModel):
    """Customer perspective — 3-4 objectives."""

    objectives: list[CustomerObjective] = Field(min_length=3, max_length=4)


class InternalProcessesPerspective(BaseModel):
    """Internal Processes perspective — 2-3 themes."""

    themes: list[InternalProcessTheme] = Field(min_length=2, max_length=3)


class OrganizationalCapacityPerspective(BaseModel):
    """Organizational Capacity perspective — exactly 3 objectives.

    One each for People / Technology / Culture. Renamed from K&N's
    "Learning and Growth" perspective to match Vector house style.
    """

    people: CapacityObjective
    technology: CapacityObjective
    culture: CapacityObjective


# ── Cross-perspective elements ─────────────────────────────────────────────


class Arrow(BaseModel):
    """A cause-and-effect arrow between two objectives.

    Per K&N: every arrow is a testable hypothesis. The `hypothesis`
    field MUST name the specific mechanism, not a generic "X enables
    Y" claim. Direction runs Capacity → Internal Process → Customer
    → Financial (within-perspective arrows are also allowed).
    """

    from_id: str = Field(min_length=2, max_length=10, alias="from")
    to_id: str = Field(min_length=2, max_length=10, alias="to")
    hypothesis: str = Field(min_length=20, max_length=500)

    model_config = {"populate_by_name": True}


class CoreValues(BaseModel):
    """Core values strip rendered at the bottom of the map.

    3-6 values. Synthesised when not explicitly published — flagged
    so the renderer can mark "(inferred)".
    """

    values: list[str] = Field(min_length=3, max_length=6)
    synthesised: bool = False
    rationale: str = Field(min_length=10, max_length=300)


# ── Top-level container ────────────────────────────────────────────────────


class StrategyMap(BaseModel):
    """AI-generated Balanced Scorecard strategy map.

    Produced by the 7-step generation chain in
    `pipeline/pipeline_steps/generate_strategy_map.py`. Persisted on
    the assessment record alongside risk scores, opportunities, EBITDA
    tree, and value chain.
    """

    vision: VisionStatement
    mission: MissionStatement
    value_proposition: ValuePropositionClassification = Field(alias="valueProposition")
    strategic_priorities: list[StrategicPriority] = Field(
        min_length=2, max_length=3, alias="strategicPriorities"
    )
    financial: FinancialPerspective
    customer: CustomerPerspective
    internal_processes: InternalProcessesPerspective = Field(alias="internalProcesses")
    organizational_capacity: OrganizationalCapacityPerspective = Field(
        alias="organizationalCapacity"
    )
    arrows: list[Arrow] = Field(min_length=5, max_length=12)
    core_values: CoreValues = Field(alias="coreValues")

    # ``populate_by_name`` lets callers construct via either snake_case
    # (Python convention) or the camelCase alias (wire format). ``extra="allow"``
    # tolerates legacy persisted records that may still carry a
    # ``whatsMissing`` field from before this change — Pydantic keeps the
    # field on the model instance but no consumer reads it, and the
    # canonical schema export drops it.
    model_config = {"populate_by_name": True, "extra": "allow"}
