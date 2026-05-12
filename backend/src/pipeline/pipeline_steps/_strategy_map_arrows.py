"""Decomposed arrows/priorities/gaps generation for the strategy-map step.

Implements `decompose-strategy-map-synthesis` Phase 2 — replaces Step 7
(single ``arrows_and_gaps`` call) with:

  Arrows bank (per-pair yes/no, ~15-25 calls in parallel):
    For every candidate ``(from_objective, to_objective)`` pair across
    the causal hierarchy
    ``capacity → internal_processes → customer → financial``, ask:
    "Does objective X enable objective Y? Yes/No, plus one-sentence
    hypothesis if Yes."
    Per-call schema: ``{enables: bool, hypothesis: string | null}``.

  Priorities (1 holistic call):
    Strategic priorities for the top header band — matches the 2-3
    Internal Process themes from Step 5.

  Gaps (1 holistic call):
    "What's Missing?" deep-dive gap candidates.

The three banks run concurrently (no inter-dependency). Assembly
filters arrows to ``enables == true`` and constructs ``Arrow`` records
from the filtered results.

This module is invoked from ``generate_strategy_map.py`` ONLY when BOTH
``GENERATE_STRATEGY_MAP_DECOMPOSED=1`` (Phase 1) and
``GENERATE_STRATEGY_MAP_DECOMPOSED_SYNTHESIS=1`` (Phase 2) are set.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from signalfield_core.utilities.future_manager import FutureManager

from src.pipeline.pipeline_steps._strategy_map_corpus import (
    load_decomposed_template,
    load_per_call_schema,
)

if TYPE_CHECKING:
    from src.pipeline.pipeline_steps.generate_strategy_map import GenerateStrategyMap
    from src.pipeline.step_timer import StepTimer

# Cap on parallelism for the arrows yes/no bank. Worst-case fan-out
# across the three causal levels is roughly 27 + 36 + 12 candidate
# pairs (capacity-3-by-internal-9, internal-9-by-customer-4,
# customer-4-by-financial-3) before filtering. We pick 25 as a soft
# upper bound on FutureManager max_workers; the actual pair count is
# determined at runtime by enumeration and FutureManager handles the
# overflow correctly.
_ARROWS_MAX_WORKERS = 25

# Hard cap on the final assembled arrow count. Matches the
# ``StrategyMap.arrows`` Pydantic constraint (``max_length=12``). The
# decomposed yes/no evaluation has no aggregate awareness — each call
# evaluates one pair in isolation — so even with a tightened prompt
# the model can over-shoot. Production hit 72 enables=true on the
# first decomposed run; this filter caps the assembled output at 12,
# balanced across the three causal levels for visual coherence on the
# rendered strategy map.
_MAX_ARROWS = 12

# Per-causal-level allocation for the post-filter. 4 + 4 + 4 = 12
# guarantees we always have a balanced top-to-bottom story flow if
# more than 12 arrows survive the yes/no evaluation. If a causal level
# returns fewer than its allotment, the remaining slots stay unfilled
# (we do NOT redistribute to other levels) — keeping a balanced
# distribution is more important than maximising the total.
_PER_LEVEL_CAP = 4

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _schema(name: str) -> dict[str, Any]:
    """Memoised per-call schema lookup (module-local cache)."""
    if name not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[name] = load_per_call_schema(name)
    return _SCHEMA_CACHE[name]


def _render(name: str, context: dict[str, Any]) -> str:
    """Render a decomposed template with ``{key}`` substitution."""
    template = load_decomposed_template(name)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return str(context[key])
        return "(unknown)"

    return _PLACEHOLDER_RE.sub(replace, template)


def enumerate_arrow_pairs(
    *,
    financial: dict[str, Any],
    customer: dict[str, Any],
    internal_processes: dict[str, Any],
    organizational_capacity: dict[str, Any],
) -> list[tuple[str, str, str, str]]:
    """Enumerate candidate arrow pairs across the causal hierarchy.

    Returns a list of ``(from_id, from_title, to_id, to_title)`` tuples
    for the three causal levels per design Decision §3:

    - ``capacity → internal_processes`` (each capacity bucket → each
      internal-process objective)
    - ``internal_processes → customer`` (each internal-process objective
      → each customer objective)
    - ``customer → financial`` (each customer objective → each financial
      objective)

    Internal-process-to-internal-process cross-theme arrows are
    intentionally excluded from the first cut (design Open Question §3).

    The returned tuples carry both IDs and titles so the per-pair prompt
    can show the objective titles to the model without needing a second
    lookup.
    """
    pairs: list[tuple[str, str, str, str]] = []

    capacity_buckets = [
        organizational_capacity["people"],
        organizational_capacity["technology"],
        organizational_capacity["culture"],
    ]
    internal_objectives: list[dict[str, Any]] = []
    for theme in internal_processes["themes"]:
        internal_objectives.extend(theme["objectives"])
    customer_objectives: list[dict[str, Any]] = customer["objectives"]
    financial_objectives: list[dict[str, Any]] = financial["objectives"]

    # Capacity → Internal Processes
    pairs.extend(
        (cap["id"], cap["title"], internal["id"], internal["title"])
        for cap in capacity_buckets
        for internal in internal_objectives
    )
    # Internal Processes → Customer
    pairs.extend(
        (internal["id"], internal["title"], cust["id"], cust["title"])
        for internal in internal_objectives
        for cust in customer_objectives
    )
    # Customer → Financial
    pairs.extend(
        (cust["id"], cust["title"], fin["id"], fin["title"])
        for cust in customer_objectives
        for fin in financial_objectives
    )

    return pairs


def run_decomposed_arrows_and_gaps(
    step: GenerateStrategyMap,
    *,
    system_prompt: str,
    context: dict[str, Any],
    timer: StepTimer,
    financial: dict[str, Any],
    customer: dict[str, Any],
    internal_processes: dict[str, Any],
    organizational_capacity: dict[str, Any],
) -> dict[str, Any]:
    """Run the arrows bank + holistic priorities + holistic gaps.

    Returns a dict shaped like the existing Step 7 output — keys
    ``strategicPriorities``, ``arrows``, ``whatsMissing`` — so the
    calling site in ``generate_strategy_map.py`` is identical regardless
    of whether the decomposed or monolithic path produced it.

    All three banks (arrows yes/no, priorities, gaps) run concurrently
    under a single ``FutureManager``.
    """
    pairs = enumerate_arrow_pairs(
        financial=financial,
        customer=customer,
        internal_processes=internal_processes,
        organizational_capacity=organizational_capacity,
    )

    arrow_schema = _schema("arrow_yesno")
    priorities_schema = _schema("arrows_priorities")
    gaps_schema = _schema("arrows_gaps")

    collected: list[tuple[str, dict[str, Any], float]] = []
    with FutureManager(
        name="GenerateStrategyMap.arrows",
        max_workers=_ARROWS_MAX_WORKERS,
    ) as manager:
        # One yes/no call per candidate pair.
        for from_id, from_title, to_id, to_title in pairs:
            arrow_context = {
                **context,
                "from_id": from_id,
                "from_title": from_title,
                "to_id": to_id,
                "to_title": to_title,
            }
            manager.submit_task(
                step._run_ai_call,
                _render("arrow_yesno", arrow_context),
                arrow_schema,
                system_prompt,
                f"arrow_{from_id}_{to_id}",
            )

        # Holistic priorities + gaps — run concurrently with the yes/no
        # bank.
        manager.submit_task(
            step._run_ai_call,
            _render("arrows_priorities", context),
            priorities_schema,
            system_prompt,
            "priorities",
        )
        manager.submit_task(
            step._run_ai_call,
            _render("arrows_gaps", context),
            gaps_schema,
            system_prompt,
            "gaps",
        )

        collected = manager.wait_for_all_and_collect_results()

    # Record per-call elapsed. Labels:
    # - ``ai_call_arrow_{from_id}_{to_id}`` per yes/no call
    # - ``ai_call_priorities``, ``ai_call_gaps`` for the holistic calls
    for label, _data, elapsed in collected:
        timer.record(f"ai_call_{label}", elapsed)

    # Partition results by label prefix.
    arrows: list[dict[str, Any]] = []
    priorities_payload: dict[str, Any] | None = None
    gaps_payload: dict[str, Any] | None = None
    for label, data, _elapsed in collected:
        if label == "priorities":
            priorities_payload = data
        elif label == "gaps":
            gaps_payload = data
        elif label.startswith("arrow_"):
            # Reconstruct (from_id, to_id) from the label suffix.
            # Label form is ``arrow_{from_id}_{to_id}``. IDs are
            # alphanumeric + period (F1, C2, I1.1, O.P) and contain no
            # underscores; splitting on the first underscore after the
            # prefix recovers the two IDs.
            suffix = label[len("arrow_") :]
            from_id, to_id = suffix.split("_", 1)
            # Hard dict access on a schema-required field. If ``enables``
            # is missing, the AI client produced an off-contract response;
            # raise loudly via KeyError rather than silently treat the
            # pair as "not enabled".
            if data["enables"] is True:
                # Schema contract: when ``enables`` is true, ``hypothesis``
                # MUST be a non-null string. The downstream ``Arrow``
                # Pydantic model declares ``hypothesis`` as a required
                # non-nullable str with ``min_length=20`` — a null value
                # there would surface as a confusing ``ValidationError``
                # deep in ``assemble_strategy_map``. Catch it here with a
                # named-pair diagnostic.
                hypothesis = data["hypothesis"]
                if hypothesis is None:
                    message = (
                        f"GenerateStrategyMap: arrow {from_id} -> {to_id} returned "
                        f"enables=true but hypothesis=null; schema contract violated"
                    )
                    raise ValueError(message)
                arrows.append(
                    {
                        "from": from_id,
                        "to": to_id,
                        "hypothesis": hypothesis,
                    }
                )

    if priorities_payload is None:
        message = "GenerateStrategyMap arrows: priorities call did not return"
        raise ValueError(message)
    if gaps_payload is None:
        message = "GenerateStrategyMap arrows: gaps call did not return"
        raise ValueError(message)

    # Post-filter cap. The decomposed yes/no evaluation has no
    # aggregate awareness so the model can return enables=true for
    # significantly more pairs than the assembled ``StrategyMap.arrows``
    # field's ``max_length=12`` permits. Cap deterministically with a
    # balanced top-to-bottom distribution.
    arrows = _cap_arrows_balanced(arrows)

    return {
        "strategicPriorities": priorities_payload["strategicPriorities"],
        "arrows": arrows,
        "whatsMissing": gaps_payload["whatsMissing"],
    }


def _causal_level(from_id: str) -> str | None:
    """Return the causal-level bucket name for a source objective ID.

    - Capacity → Internal Processes:  source IDs start with ``"O."``
      (``O.P``, ``O.T``, ``O.C``).
    - Internal Processes → Customer:  source IDs start with ``"I"``.
    - Customer → Financial:           source IDs start with ``"C"``.

    Returns ``None`` if the ID shape doesn't match any expected level —
    callers should treat this as a programming error in pair
    enumeration.
    """
    if from_id.startswith("O."):
        return "capacity_to_internal"
    if from_id.startswith("I"):
        return "internal_to_customer"
    if from_id.startswith("C"):
        return "customer_to_financial"
    return None


def _cap_arrows_balanced(arrows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cap the assembled arrows list at ``_MAX_ARROWS`` with balanced levels.

    When the model returns more enables=true responses than the
    assembled ``StrategyMap.arrows`` field permits (``max_length=12``),
    we need a deterministic way to pick which arrows survive. The
    balanced strategy:

    - Bucket arrows by causal level (capacity→internal, internal→
      customer, customer→financial) — the order arrows were added
      already follows this enumeration order in ``enumerate_arrow_pairs``.
    - Keep up to ``_PER_LEVEL_CAP`` arrows from each level, in the
      order they were added (which itself follows the enumeration
      order — so earlier-enumerated objective IDs are preferred).
    - Concatenate the three level lists back in top-to-bottom order
      so the assembled output narrates the strategy from capacity up
      to financial outcomes.

    If the total arrow count is already ``<= _MAX_ARROWS``, return the
    input unchanged.
    """
    if len(arrows) <= _MAX_ARROWS:
        return arrows

    by_level: dict[str, list[dict[str, Any]]] = {
        "capacity_to_internal": [],
        "internal_to_customer": [],
        "customer_to_financial": [],
    }
    for arrow in arrows:
        level = _causal_level(arrow["from"])
        if level is None:
            # An arrow with an unrecognised source ID indicates a
            # programming error in pair enumeration. Fail fast rather
            # than silently drop it.
            message = (
                f"GenerateStrategyMap: arrow source ID {arrow['from']!r} does not "
                f"match any known causal-level prefix (O./I/C); cannot bucket "
                f"for post-filter."
            )
            raise ValueError(message)
        by_level[level].append(arrow)

    return (
        by_level["capacity_to_internal"][:_PER_LEVEL_CAP]
        + by_level["internal_to_customer"][:_PER_LEVEL_CAP]
        + by_level["customer_to_financial"][:_PER_LEVEL_CAP]
    )
