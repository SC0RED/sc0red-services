"""Tests for the data-integrity audit rule (report-data-integrity spec).

Mirrors the detection logic in ``scripts/audit.sh`` ("fact-bearing builders
render a placeholder, not a default"): every ``build_programmatic_*`` builder
MUST carry an insufficient-data (``grounded=False``) branch so an unmatched
input renders the placeholder rather than silently fabricating a default. The
rule is a forward invariant (required branch present) rather than an anti-pattern
grep, so it cannot be bypassed by renaming the default-template constant.
"""

from __future__ import annotations

import re
from pathlib import Path

_BUILDERS_DIR = Path(__file__).resolve().parents[3] / "src" / "pipeline" / "pipeline_steps"
_PLACEHOLDER_RE = re.compile(r"grounded\s*=\s*False|insufficient_data")


def _missing_grounded_branch(source: str) -> bool:
    """Replicate the audit rule: True if a builder lacks the placeholder branch."""
    if "def build_programmatic" not in source:
        return False
    return not _PLACEHOLDER_RE.search(source)


class TestAuditRuleFires:
    def test_builder_without_placeholder_branch_is_flagged(self):
        bad = (
            "def build_programmatic_thing(profile):\n"
            "    template = _resolve(profile.business_model)\n"
            "    return Result(template)\n"
        )
        assert _missing_grounded_branch(bad) is True

    def test_builder_with_placeholder_branch_passes(self):
        good = (
            "def build_programmatic_thing(profile):\n"
            "    resolved = _resolve(profile.business_model)\n"
            "    if resolved is None:\n"
            "        return Result(grounded=False)\n"
            "    return Result(resolved)\n"
        )
        assert _missing_grounded_branch(good) is False

    def test_renamed_default_constant_does_not_bypass_the_rule(self):
        # A builder that reintroduces a silent default under a different constant
        # name is still caught, because the rule requires the grounded branch.
        sneaky = (
            "def build_programmatic_thing(profile):\n"
            "    return TEMPLATES.get(profile.business_model, FALLBACK_TEMPLATE)\n"
        )
        assert _missing_grounded_branch(sneaky) is True

    def test_non_builder_module_is_ignored(self):
        templates_module = "FALLBACK_TEMPLATE = 'saas'\n"
        assert _missing_grounded_branch(templates_module) is False


class TestRealBuildersPass:
    def test_ebitda_and_value_chain_builders_have_placeholder_branch(self):
        for name in ("build_ebitda_tree.py", "build_value_chain.py"):
            source = (_BUILDERS_DIR / name).read_text()
            assert _missing_grounded_branch(source) is False, (
                f"{name} is missing its insufficient-data (grounded=False) branch"
            )
