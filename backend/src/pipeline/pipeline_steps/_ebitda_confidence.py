"""Derivation-provenance confidence labelling for the EBITDA tree.

Owns ``_compute_confidence``, which converts the ``size_matched`` input axis into
a (level, basis) tuple per the ebitda-tree-confidence capability spec. A rendered
tree always derives from a matched template (an unmatched business model
short-circuits to the insufficient-data placeholder before this is reached), so
the level is "high" when size resolved and "medium" when it defaulted — never
"low". Lives in its own module to keep the main builder file under the 400-line
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
    company_size: str,
    size_matched: bool,
    node_kind: Literal["revenue", "cost"],
) -> tuple[Literal["high", "medium"], str]:
    """Compute the confidence (level, basis) pair for a leaf node.

    The level reflects how cleanly the build inputs resolved against the
    deterministic logic in ``build_ebitda_tree``. A rendered tree always derives
    from a *matched* template — an unmatched business model short-circuits to the
    insufficient-data placeholder before this function is reached (see
    ``build_programmatic_ebitda_tree``), so the only remaining axis is whether
    ``company_size`` resolved against a known bracket:

    * size matched → "high"   — both inputs gave usable signal
    * size defaulted → "medium" — the size bracket defaulted

    The previously-specified "both inputs defaulted → low" outcome is unreachable
    for a rendered tree because the template-default path that produced it was
    removed. See the ebitda-tree-confidence spec for the canonical rules.

    The ``basis`` string is a 1-2 sentence human-readable explanation that names
    the resolved template and the (resolved or defaulted) size bracket; it is
    phrased differently for revenue vs cost provenance because the inputs flow
    through differently (revenue is computed directly from size times
    rev-per-employee; cost is computed by applying template margins to revenue,
    so cost provenance always references "industry-benchmark margin" in addition
    to the upstream revenue inputs).
    """
    template_clause = f"a {template.label} template (matched on business model)"
    size_clause = (
        f"a known size bracket ({company_size!r})"
        if size_matched
        else "a defaulted mid-market size bracket (no matching company-size signal)"
    )

    level: Literal["high", "medium"] = "high" if size_matched else "medium"

    if node_kind == "revenue":
        basis = f"Revenue derived from {template_clause} applied to {size_clause}."
    else:
        basis = (
            f"Cost derived from industry-benchmark margins on {template_clause}, "
            f"applied to revenue estimated from {size_clause}."
        )
    return level, basis
