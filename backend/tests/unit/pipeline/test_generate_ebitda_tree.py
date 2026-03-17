"""Tests for EBITDA tree constants, schemas, and node builder."""

from src.pipeline.pipeline_steps.generate_ebitda_tree import (
    EBITDA_SYSTEM_PROMPT,
    EBITDA_TREE_SCHEMA,
    build_ebitda_node,
    build_ebitda_prompt,
)


class TestBuildEbitdaNode:
    def test_builds_flat_node(self):
        node = build_ebitda_node(
            {
                "id": "revenue",
                "label": "Total Revenue",
                "type": "revenue",
                "value_range": "$10M-$50M",
                "percentage_of_parent": None,
                "description": "All revenue",
                "linked_opportunity_indices": [0, 1],
                "children": [],
            }
        )
        assert node.id == "revenue"
        assert node.type == "revenue"
        assert node.linked_opportunity_indices == [0, 1]
        assert node.children == []

    def test_builds_nested_nodes(self):
        node = build_ebitda_node(
            {
                "id": "revenue",
                "label": "Revenue",
                "type": "revenue",
                "value_range": "$10M-$50M",
                "percentage_of_parent": None,
                "description": "Top",
                "linked_opportunity_indices": [],
                "children": [
                    {
                        "id": "subs",
                        "label": "Subscriptions",
                        "type": "revenue",
                        "value_range": "$8M-$40M",
                        "percentage_of_parent": 80,
                        "description": "SaaS subs",
                        "linked_opportunity_indices": [0],
                        "children": [],
                    },
                ],
            }
        )
        assert len(node.children) == 1
        assert node.children[0].id == "subs"
        assert node.children[0].linked_opportunity_indices == [0]

    def test_builds_node_without_linked_indices(self):
        """Nodes from AI response won't have linked_opportunity_indices — defaults to empty."""
        node = build_ebitda_node(
            {
                "id": "cogs",
                "label": "COGS",
                "type": "cost",
                "value_range": "$3M-$15M",
                "percentage_of_parent": None,
                "description": "Cost of goods",
                "children": [],
            }
        )
        assert node.linked_opportunity_indices == []

    def test_builds_node_with_optional_fields(self):
        node = build_ebitda_node(
            {
                "id": "margin",
                "label": "Gross Margin",
                "type": "margin",
                "value_range": "$5M-$10M",
                "percentage_of_parent": 60,
                "description": "Gross margin",
                "children": [],
            }
        )
        assert node.value_range == "$5M-$10M"
        assert node.percentage_of_parent == 60

    def test_missing_required_field_raises(self):
        """Missing a required field should raise KeyError — fail-fast."""
        import pytest

        with pytest.raises(KeyError):
            build_ebitda_node(
                {
                    "id": "broken",
                    "label": "Broken",
                    "type": "revenue",
                    "description": "Missing children",
                    "value_range": "$1M",
                    "percentage_of_parent": None,
                    # "children" missing — should fail
                }
            )


class TestBuildEbitdaPrompt:
    def test_prompt_includes_profile_and_risk(self):
        profile = {"company_name": "Acme Corp", "industry": "SaaS"}
        assessment = {
            "overall_score": 7.0,
            "tier": "high",
            "analysis_summary": "High competitive risk",
        }
        prompt = build_ebitda_prompt(profile, assessment)
        assert "Acme Corp" in prompt
        assert "7.0/10" in prompt
        assert "high risk" in prompt.lower()
        assert "EBITDA" in prompt

    def test_prompt_has_tree_structure_guidelines(self):
        prompt = build_ebitda_prompt(
            {"company_name": "Test"},
            {"overall_score": 5.0, "tier": "moderate", "analysis_summary": "Test"},
        )
        assert "Revenue" in prompt
        assert "Gross Profit" in prompt
        assert "operating expense" in prompt.lower()


class TestSchemas:
    def test_system_prompt_is_non_empty_string(self):
        assert isinstance(EBITDA_SYSTEM_PROMPT, str)
        assert len(EBITDA_SYSTEM_PROMPT) > 50

    def test_tree_schema_has_required_fields(self):
        assert "summary" in EBITDA_TREE_SCHEMA["properties"]
        assert "nodes" in EBITDA_TREE_SCHEMA["properties"]
        assert "revenue_estimate" in EBITDA_TREE_SCHEMA["properties"]
        assert "ebitda_estimate" in EBITDA_TREE_SCHEMA["properties"]
