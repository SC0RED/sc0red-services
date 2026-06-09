"""Tests for sanitize_implementation_steps — strips leaked detail-field tokens.

Guards against the structured-output malformation where the model appends the
other detail fields' names and values as extra "steps" (observed on a real
Century scan, OPP#0002).
"""

from __future__ import annotations

from src.pipeline.pipeline_steps.detail_opportunity import sanitize_implementation_steps


def test_strips_leaked_field_names_and_values():
    # The exact malformation shape from the production Century run.
    detail_data = {
        "implementation_steps": [
            "Map Century's top 25 client-intake and servicing interactions...",
            "Integrate the copilot with CRM/case-management and payment-status data...",
            "Pilot with one client segment or geography for 6-8 weeks...",
            "timeline",
            "Medium-term (3-9 months)",
            "investment_range",
            "$100K-$500K",
            "roi_estimate",
            "Reduces routine workload ~35% for roughly 120% first-year ROI.",
            "investment_value_usd",
            ",",
        ],
        "timeline": "Medium-term (3-9 months)",
        "investment_range": "$100K-$500K",
        "roi_estimate": "Reduces routine workload ~35% for roughly 120% first-year ROI.",
        "investment_value_usd": 300000,
        "roi_estimate_pct": 120,
    }
    steps = sanitize_implementation_steps(detail_data)
    assert len(steps) == 3
    assert steps[0].startswith("Map Century")
    assert steps[1].startswith("Integrate the copilot")
    assert steps[2].startswith("Pilot with one client segment")
    # None of the leaked tokens survive.
    for leaked in ("timeline", "investment_range", "roi_estimate", "investment_value_usd", ","):
        assert leaked not in steps
    assert "Medium-term (3-9 months)" not in steps
    assert "$100K-$500K" not in steps


def test_clean_steps_pass_through_unchanged():
    detail_data = {
        "implementation_steps": ["Step one in full.", "Step two in full.", "Step three in full."],
        "timeline": "Quick Win (1-3 months)",
        "investment_range": "$50K-$100K",
        "roi_estimate": "30% reduction in support cost.",
        "investment_value_usd": 75000,
        "roi_estimate_pct": 30,
    }
    assert sanitize_implementation_steps(detail_data) == [
        "Step one in full.",
        "Step two in full.",
        "Step three in full.",
    ]


def test_caps_to_max_steps():
    detail_data = {
        "implementation_steps": [f"Genuine step number {n} described in full." for n in range(8)],
        "timeline": "x",
        "investment_range": "y",
        "roi_estimate": "z",
        "investment_value_usd": 1,
        "roi_estimate_pct": 1,
    }
    assert len(sanitize_implementation_steps(detail_data)) == 5


def test_null_numeric_fields_do_not_drop_real_steps():
    # Schema allows null for the numeric axes; "None" must not leak into the
    # filter and clobber a real step.
    detail_data = {
        "implementation_steps": ["Step A in full.", "Step B in full.", "Step C in full."],
        "timeline": "Quick Win (1-3 months)",
        "investment_range": "$50K-$100K",
        "roi_estimate": "30% reduction.",
        "investment_value_usd": None,
        "roi_estimate_pct": None,
    }
    assert sanitize_implementation_steps(detail_data) == [
        "Step A in full.",
        "Step B in full.",
        "Step C in full.",
    ]


def test_missing_or_non_list_is_safe():
    assert sanitize_implementation_steps({}) == []
    assert sanitize_implementation_steps({"implementation_steps": "not a list"}) == []
