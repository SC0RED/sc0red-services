"""Tests for rank_opportunities — pure logic, no IO or AI calls."""

import pytest

from src.pipeline.pipeline_steps.rank_opportunities import (
    IMPACT_RATING_SCORES,
    deduplicate_ideations,
    derive_top_three_actions,
    rank_ideations,
)


def _make_ideation(
    title: str = "Deploy AI chatbot",
    impact_rating: str = "High",
    risk_category: str = "competitive_displacement",
    **kwargs: object,
) -> dict[str, object]:
    return {
        "title": title,
        "description": "A test ideation",
        "value_lever": "Revenue Side",
        "strategic_category": "Competitive Moat",
        "impact_rating": impact_rating,
        "risk_category": risk_category,
        **kwargs,
    }


_RISK_SCORES: dict[str, float] = {
    "competitive_displacement": 8.0,
    "technology_obsolescence": 7.0,
    "talent_workforce": 6.0,
    "margin_compression": 5.0,
    "customer_behavior": 4.0,
    "regulatory_compliance": 3.0,
    "supply_chain": 2.0,
    "data_ip": 1.0,
}


class TestDeduplicateIdeations:
    def test_identical_titles_keeps_one(self):
        ideations = [
            _make_ideation("Deploy AI chatbot", risk_category="competitive_displacement"),
            _make_ideation("Deploy AI chatbot", risk_category="technology_obsolescence"),
        ]
        result = deduplicate_ideations(ideations, _RISK_SCORES)
        assert len(result) == 1
        # Higher risk score category kept
        assert result[0]["risk_category"] == "competitive_displacement"

    def test_overlapping_titles_deduplicated(self):
        ideations = [
            _make_ideation("Deploy AI customer chatbot", risk_category="competitive_displacement"),
            _make_ideation("Deploy AI support chatbot", risk_category="technology_obsolescence"),
        ]
        result = deduplicate_ideations(ideations, _RISK_SCORES)
        # "deploy", "ai", "chatbot" overlap = 3 words; smaller set = 3 words → 100% > 60%
        assert len(result) == 1

    def test_dissimilar_titles_kept(self):
        ideations = [
            _make_ideation("Deploy AI chatbot for support", risk_category="competitive_displacement"),
            _make_ideation("Automate supply chain logistics", risk_category="supply_chain"),
        ]
        result = deduplicate_ideations(ideations, _RISK_SCORES)
        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        result = deduplicate_ideations([], _RISK_SCORES)
        assert result == []

    def test_single_ideation_returned(self):
        ideations = [_make_ideation()]
        result = deduplicate_ideations(ideations, _RISK_SCORES)
        assert len(result) == 1

    def test_keeps_higher_risk_score_category(self):
        ideations = [
            _make_ideation("Build predictive model", risk_category="supply_chain"),  # score=2
            _make_ideation("Build predictive model", risk_category="competitive_displacement"),  # score=8
        ]
        result = deduplicate_ideations(ideations, _RISK_SCORES)
        assert len(result) == 1
        assert result[0]["risk_category"] == "competitive_displacement"


class TestRankIdeations:
    def test_high_before_medium_before_low(self):
        ideations = [
            _make_ideation("Low idea", impact_rating="Low", risk_category="supply_chain"),
            _make_ideation("High idea", impact_rating="High", risk_category="supply_chain"),
            _make_ideation("Medium idea", impact_rating="Medium", risk_category="supply_chain"),
        ]
        result = rank_ideations(ideations, _RISK_SCORES)
        assert result[0]["title"] == "High idea"
        assert result[1]["title"] == "Medium idea"
        assert result[2]["title"] == "Low idea"

    def test_tie_broken_by_risk_score(self):
        ideations = [
            _make_ideation("Idea B", impact_rating="High", risk_category="supply_chain"),  # score=2
            _make_ideation("Idea A", impact_rating="High", risk_category="competitive_displacement"),  # score=8
        ]
        result = rank_ideations(ideations, _RISK_SCORES)
        assert result[0]["title"] == "Idea A"
        assert result[1]["title"] == "Idea B"

    def test_max_count_limits_results(self):
        ideations = [_make_ideation(f"Idea {i}") for i in range(10)]
        result = rank_ideations(ideations, _RISK_SCORES, max_count=3)
        assert len(result) == 3

    def test_max_count_default_is_five(self):
        ideations = [_make_ideation(f"Idea {i}") for i in range(10)]
        result = rank_ideations(ideations, _RISK_SCORES)
        assert len(result) == 5

    def test_fewer_than_max_count_returns_all(self):
        ideations = [_make_ideation("Only one")]
        result = rank_ideations(ideations, _RISK_SCORES, max_count=5)
        assert len(result) == 1

    def test_empty_list_returns_empty(self):
        result = rank_ideations([], _RISK_SCORES)
        assert result == []


class TestDeriveTopThreeActions:
    def test_derives_three_actions(self):
        ranked = [
            _make_ideation("Action Alpha"),
            _make_ideation("Action Beta"),
            _make_ideation("Action Gamma"),
            _make_ideation("Action Delta"),
        ]
        result = derive_top_three_actions(ranked)
        assert result == ["Action Alpha", "Action Beta", "Action Gamma"]

    def test_fewer_than_three_ideations(self):
        ranked = [_make_ideation("Only One")]
        result = derive_top_three_actions(ranked)
        assert result == ["Only One"]

    def test_empty_list_returns_empty(self):
        result = derive_top_three_actions([])
        assert result == []


class TestImpactRatingScores:
    def test_scores_mapping(self):
        assert IMPACT_RATING_SCORES == {"High": 3, "Medium": 2, "Low": 1}
