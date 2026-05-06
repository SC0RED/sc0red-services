"""Derivation-provenance confidence labelling for the EBITDA tree.

Owns ``_compute_confidence``, which converts the (template_matched, size_matched)
input pair into a (level, basis) tuple per the ebitda-tree-confidence capability
spec. Lives in its own module to keep the main builder file under the 400-line
limit and to make the confidence rules easy to find when iterating on copy.

Module-private — exported only to ``build_ebitda_tree.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.pipeline.pipeline_steps._ebitda_templates import _Template


def _compute_confidence(
    *,
    template: _Template,
    template_matched: bool,
    company_size: str,
    size_matched: bool,
    node_kind: Literal["revenue", "cost"],
) -> tuple[Literal["high", "medium", "low"], str]:
    """Compute the confidence (level, basis) pair for a leaf node.

    The level reflects how cleanly the build inputs resolved against the
    deterministic logic in ``build_ebitda_tree``. ``template_matched`` and
    ``size_matched`` each indicate whether their input resolved against a known
    entry; both booleans together pick the level:

    * both True  → "high"   — both inputs gave usable signal
    * exactly 1  → "medium" — one input defaulted
    * both False → "low"    — both inputs defaulted; figure is a generic guess

    The ``basis`` string is a 1-2 sentence human-readable explanation that names
    the resolved input(s) and the defaulted one(s); it is phrased differently
    for revenue vs cost provenance because the inputs flow through differently
    (revenue is computed directly from size times rev-per-employee; cost is
    computed by applying template margins to revenue, so cost provenance always
    references "industry-benchmark margin" in addition to the upstream revenue
    inputs).
    See the ebitda-tree-confidence spec for the canonical rules.
    """
    template_clause = (
        f"a {template.label} template (matched on business model)"
        if template_matched
        else f"a defaulted {template.label} template (no matching business model keyword)"
    )
    size_clause = (
        f"a known size bracket ({company_size!r})"
        if size_matched
        else "a defaulted mid-market size bracket (no matching company-size signal)"
    )

    if template_matched and size_matched:
        level: Literal["high", "medium", "low"] = "high"
    elif template_matched or size_matched:
        level = "medium"
    else:
        level = "low"

    if node_kind == "revenue":
        basis = f"Revenue derived from {template_clause} applied to {size_clause}."
    else:
        basis = (
            f"Cost derived from industry-benchmark margins on {template_clause}, "
            f"applied to revenue estimated from {size_clause}."
        )
    return level, basis
