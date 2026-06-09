"""Tests for the data-integrity audit rule (report-data-integrity spec).

Mirrors the detection logic in ``scripts/audit.sh``: every fact-surface assembler
(``assemble_ebitda_tree`` / ``assemble_value_chain``) MUST carry an
insufficient-data (``grounded=False``) branch so an ungroundable input renders
the placeholder rather than a fabricated surface. The rule is a forward invariant
(required branch present), so it cannot be bypassed by renaming a helper.
"""

from __future__ import annotations

import re
from pathlib import Path

_BUILDERS_DIR = Path(__file__).resolve().parents[3] / "src" / "pipeline" / "pipeline_steps"
_ASSEMBLER_RE = re.compile(r"def assemble_(ebitda_tree|value_chain)")
_PLACEHOLDER_RE = re.compile(r"grounded\s*=\s*False|insufficient_data")


def _missing_grounded_branch(source: str) -> bool:
    """Replicate the audit rule: True if an assembler lacks the placeholder branch."""
    if not _ASSEMBLER_RE.search(source):
        return False
    return not _PLACEHOLDER_RE.search(source)


class TestAuditRuleFires:
    def test_assembler_without_placeholder_branch_is_flagged(self):
        bad = "def assemble_ebitda_tree(facts, name):\n    return EbitdaTreeResult(nodes=[...])\n"
        assert _missing_grounded_branch(bad) is True

    def test_assembler_with_placeholder_branch_passes(self):
        good = (
            "def assemble_ebitda_tree(facts, name):\n"
            "    if bad_range:\n"
            "        return EbitdaTreeResult(grounded=False)\n"
            "    return EbitdaTreeResult(nodes=[...])\n"
        )
        assert _missing_grounded_branch(good) is False

    def test_non_assembler_module_is_ignored(self):
        assert _missing_grounded_branch("def helper():\n    return 1\n") is False


class TestRealAssemblersPass:
    def test_ebitda_and_value_chain_assemblers_have_placeholder_branch(self):
        for name in ("build_ebitda_tree.py", "build_value_chain.py"):
            source = (_BUILDERS_DIR / name).read_text()
            assert _missing_grounded_branch(source) is False, (
                f"{name} is missing its insufficient-data (grounded=False) branch"
            )
