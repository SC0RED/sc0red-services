"""Tests for the positional ID assignment helpers in `_strategy_map_assembly`.

Per `optimize-strategy-map-latency` Decision §2, IDs are assigned by the
assembly layer from title-list order so parallel detail calls can omit
the ``id`` field from their per-call schemas. These tests pin that
behaviour — IDs MUST be `F1`/`F2`/`F3`, `C1`-`C4`, `I{theme}.{obj}`,
`O.P`/`O.T`/`O.C` exactly as the strategy-map output schema requires.
"""

from __future__ import annotations

import pytest

from src.pipeline.pipeline_steps._strategy_map_assembly import (
    build_capacity_objectives,
    build_customer_objectives,
    build_financial_objectives,
    build_internal_themes,
)


class TestBuildFinancialObjectives:
    def test_assigns_F1_F2_F3_in_title_list_order(self):
        titles = ["Grow revenue", "Drive efficiency", "Maximise ROIC"]
        details = [
            {"definition": "d1", "category": "revenue_growth", "confidence": "HIGH", "rationale_source": "x"},
            {"definition": "d2", "category": "productivity", "confidence": "MEDIUM", "rationale_source": "y"},
            {"definition": "d3", "category": "productivity", "confidence": "LOW", "rationale_source": None},
        ]
        objectives = build_financial_objectives(titles, details)
        assert [o["id"] for o in objectives] == ["F1", "F2", "F3"]
        assert [o["title"] for o in objectives] == titles
        # Detail fields propagate verbatim
        assert objectives[0]["category"] == "revenue_growth"
        assert objectives[1]["confidence"] == "MEDIUM"
        assert objectives[2]["rationale_source"] is None

    def test_raises_when_titles_and_details_have_different_lengths(self):
        # Length mismatch indicates an orchestration bug — surfacing it as
        # ValueError beats producing a strategy map with N titles but
        # N-1 details, which would silently blow up Pydantic validation
        # downstream with a less actionable error.
        with pytest.raises(ValueError, match="financial assembly"):
            build_financial_objectives(["a", "b", "c"], [{}, {}])


class TestBuildCustomerObjectives:
    def test_assigns_C1_C2_C3_C4_in_title_list_order(self):
        titles = ["Want fresh products", "Want loyalty rewards", "Want fast service", "Want quality"]
        details = [
            {"definition": "d1", "panel": "consumer", "confidence": "HIGH", "rationale_source": "x"},
            {"definition": "d2", "panel": "consumer", "confidence": "MEDIUM", "rationale_source": "y"},
            {"definition": "d3", "panel": "consumer", "confidence": "HIGH", "rationale_source": None},
            {"definition": "d4", "panel": "channel", "confidence": "LOW", "rationale_source": "z"},
        ]
        objectives = build_customer_objectives(titles, details)
        assert [o["id"] for o in objectives] == ["C1", "C2", "C3", "C4"]
        assert objectives[3]["panel"] == "channel"

    def test_handles_3_objective_minimum(self):
        # Customer perspective allows 3-4 objectives; verify the 3-objective
        # case still produces correct IDs without trailing C4.
        titles = ["t1", "t2", "t3"]
        details = [
            {"definition": "d", "panel": "consumer", "confidence": "HIGH", "rationale_source": None}
            for _ in range(3)
        ]
        objectives = build_customer_objectives(titles, details)
        assert [o["id"] for o in objectives] == ["C1", "C2", "C3"]


class TestBuildInternalThemes:
    def test_assigns_themed_ids_per_theme_and_objective(self):
        themes_meta = [
            {"name": "Differentiate the offer", "supports_financial_objectives": ["F1"]},
            {"name": "Improve throughput", "supports_financial_objectives": ["F2"]},
        ]
        titles_per_theme = [
            ["Develop signature offers", "Refresh ambience"],
            ["Improve E2E throughput"],
        ]
        details_per_theme = [
            [
                {"definition": "d", "category": "innovation", "confidence": "HIGH", "rationale_source": None},
                {"definition": "d", "category": "innovation", "confidence": "MEDIUM", "rationale_source": None},
            ],
            [{"definition": "d", "category": "operational_excellence", "confidence": "HIGH", "rationale_source": None}],
        ]

        themes = build_internal_themes(themes_meta, titles_per_theme, details_per_theme)

        # Theme 1: I1.1, I1.2 (1-indexed, matches `^I[1-3]\.[1-9]$` regex)
        assert [o["id"] for o in themes[0]["objectives"]] == ["I1.1", "I1.2"]
        # Theme 2: I2.1 only
        assert [o["id"] for o in themes[1]["objectives"]] == ["I2.1"]
        # Theme metadata propagates
        assert themes[0]["name"] == "Differentiate the offer"
        assert themes[0]["supports_financial_objectives"] == ["F1"]
        # Detail fields propagate
        assert themes[0]["objectives"][1]["confidence"] == "MEDIUM"

    def test_raises_on_outer_length_mismatch(self):
        # 3 themes but only 2 title lists — this is an orchestration bug,
        # surfaces as ValueError so the failure is loud in CloudWatch.
        with pytest.raises(ValueError, match="Internal-processes assembly mismatch"):
            build_internal_themes(
                [
                    {"name": "A", "supports_financial_objectives": ["F1"]},
                    {"name": "B", "supports_financial_objectives": ["F1"]},
                    {"name": "C", "supports_financial_objectives": ["F1"]},
                ],
                [["t1"], ["t2"]],
                [[{"d": 1}], [{"d": 1}], [{"d": 1}]],
            )

    def test_raises_on_inner_length_mismatch(self):
        # Theme has 2 titles but only 1 detail — _check_same_length surfaces it.
        with pytest.raises(ValueError, match="internal theme 1"):
            build_internal_themes(
                [{"name": "A", "supports_financial_objectives": ["F1"]}],
                [["t1", "t2"]],
                [[{"definition": "d"}]],
            )


class TestBuildCapacityObjectives:
    def test_assigns_O_P_O_T_O_C_to_fixed_buckets(self):
        titles = {
            "people": "Develop our associates",
            "technology": "Deliver reliable systems",
            "culture": "Live our values",
        }
        details = {
            "people": {"definition": "d", "confidence": "MEDIUM", "rationale_source": None},
            "technology": {"definition": "d", "confidence": "HIGH", "rationale_source": None},
            "culture": {"definition": "d", "confidence": "LOW", "rationale_source": "x"},
        }
        result = build_capacity_objectives(titles, details)
        # Capacity is bucket-keyed (people / technology / culture), each with O.P / O.T / O.C IDs.
        assert result["people"]["id"] == "O.P"
        assert result["technology"]["id"] == "O.T"
        assert result["culture"]["id"] == "O.C"
        # Title and detail propagate
        assert result["people"]["title"] == "Develop our associates"
        assert result["culture"]["confidence"] == "LOW"
        assert result["culture"]["rationale_source"] == "x"

    def test_raises_when_titles_missing_a_bucket(self):
        titles = {"people": "t", "technology": "t"}  # missing culture
        details = {
            "people": {"definition": "d", "confidence": "HIGH", "rationale_source": None},
            "technology": {"definition": "d", "confidence": "HIGH", "rationale_source": None},
            "culture": {"definition": "d", "confidence": "HIGH", "rationale_source": None},
        }
        with pytest.raises(ValueError, match="Capacity titles missing"):
            build_capacity_objectives(titles, details)  # type: ignore[arg-type]

    def test_raises_when_details_missing_a_bucket(self):
        titles = {"people": "t", "technology": "t", "culture": "t"}
        details = {
            "people": {"definition": "d", "confidence": "HIGH", "rationale_source": None},
            "culture": {"definition": "d", "confidence": "HIGH", "rationale_source": None},
            # missing technology
        }
        with pytest.raises(ValueError, match="Capacity details missing"):
            build_capacity_objectives(titles, details)  # type: ignore[arg-type]
