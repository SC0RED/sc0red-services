"""Tests for EBITDA tree constants, schemas, node builder, and flat tree reconstruction."""

from typing import Any

import pytest

from src.models.model_company import EbitdaNode
from src.pipeline.pipeline_steps.generate_ebitda_tree import (
    EBITDA_SYSTEM_PROMPT,
    EBITDA_TREE_SCHEMA,
    build_ebitda_prompt,
    build_ebitda_tree_from_flat_nodes,
)


def build_ebitda_node(data: dict[str, Any]) -> EbitdaNode:
    """Recursively build an EbitdaNode from a nested dict (test helper)."""
    children = [build_ebitda_node(child) for child in data["children"]]
    return EbitdaNode(
        id=data["id"],
        label=data["label"],
        type=data["type"],
        value_range=data["value_range"],
        percentage_of_parent=data["percentage_of_parent"],
        description=data["description"],
        linked_opportunity_indices=data.get("linked_opportunity_indices", []),
        children=children,
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


class TestBuildEbitdaTreeFromFlatNodes:
    def test_reconstructs_simple_tree(self):
        flat_nodes = [
            {
                "id": "revenue",
                "parent_id": None,
                "label": "Total Revenue",
                "type": "revenue",
                "value_range": "$10M-$50M",
                "percentage_of_parent": None,
                "description": "All revenue",
            },
            {
                "id": "subs",
                "parent_id": "revenue",
                "label": "Subscriptions",
                "type": "revenue",
                "value_range": "$8M-$40M",
                "percentage_of_parent": 80,
                "description": "SaaS subscriptions",
            },
            {
                "id": "services",
                "parent_id": "revenue",
                "label": "Professional Services",
                "type": "revenue",
                "value_range": "$2M-$10M",
                "percentage_of_parent": 20,
                "description": "Consulting",
            },
        ]
        roots = build_ebitda_tree_from_flat_nodes(flat_nodes)

        assert len(roots) == 1
        assert roots[0].id == "revenue"
        assert len(roots[0].children) == 2
        assert roots[0].children[0].id == "subs"
        assert roots[0].children[1].id == "services"
        assert roots[0].children[0].percentage_of_parent == 80

    def test_reconstructs_multiple_top_level_nodes(self):
        flat_nodes = [
            {
                "id": "revenue",
                "parent_id": None,
                "label": "Revenue",
                "type": "revenue",
                "value_range": "$10M",
                "percentage_of_parent": None,
                "description": "Rev",
            },
            {
                "id": "cogs",
                "parent_id": None,
                "label": "COGS",
                "type": "cost",
                "value_range": "$3M",
                "percentage_of_parent": None,
                "description": "Costs",
            },
            {
                "id": "ebitda",
                "parent_id": None,
                "label": "EBITDA",
                "type": "subtotal",
                "value_range": "$2M",
                "percentage_of_parent": None,
                "description": "Earnings",
            },
        ]
        roots = build_ebitda_tree_from_flat_nodes(flat_nodes)

        assert len(roots) == 3
        assert roots[0].id == "revenue"
        assert roots[1].id == "cogs"
        assert roots[2].id == "ebitda"

    def test_reconstructs_deep_nesting(self):
        flat_nodes = [
            {
                "id": "revenue",
                "parent_id": None,
                "label": "Revenue",
                "type": "revenue",
                "value_range": "$10M",
                "percentage_of_parent": None,
                "description": "Rev",
            },
            {
                "id": "subs",
                "parent_id": "revenue",
                "label": "Subscriptions",
                "type": "revenue",
                "value_range": "$8M",
                "percentage_of_parent": 80,
                "description": "Subs",
            },
            {
                "id": "enterprise",
                "parent_id": "subs",
                "label": "Enterprise",
                "type": "revenue",
                "value_range": "$6M",
                "percentage_of_parent": 75,
                "description": "Enterprise tier",
            },
        ]
        roots = build_ebitda_tree_from_flat_nodes(flat_nodes)

        assert len(roots) == 1
        assert roots[0].id == "revenue"
        assert len(roots[0].children) == 1
        assert roots[0].children[0].id == "subs"
        assert len(roots[0].children[0].children) == 1
        assert roots[0].children[0].children[0].id == "enterprise"

    def test_empty_list_returns_empty(self):
        roots = build_ebitda_tree_from_flat_nodes([])
        assert roots == []

    def test_nodes_have_empty_linked_opportunity_indices(self):
        """Freshly reconstructed nodes should have empty linked_opportunity_indices."""
        flat_nodes = [
            {
                "id": "revenue",
                "parent_id": None,
                "label": "Revenue",
                "type": "revenue",
                "value_range": "$10M",
                "percentage_of_parent": None,
                "description": "Rev",
            },
        ]
        roots = build_ebitda_tree_from_flat_nodes(flat_nodes)
        assert roots[0].linked_opportunity_indices == []


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

    def test_prompt_requests_flat_format(self):
        prompt = build_ebitda_prompt(
            {"company_name": "Test"},
            {"overall_score": 5.0, "tier": "moderate", "analysis_summary": "Test"},
        )
        assert "FLAT LIST" in prompt
        assert "parent_id" in prompt
        assert "Do NOT nest" in prompt


class TestSchemas:
    def test_system_prompt_is_non_empty_string(self):
        assert isinstance(EBITDA_SYSTEM_PROMPT, str)
        assert len(EBITDA_SYSTEM_PROMPT) > 50

    def test_tree_schema_has_required_fields(self):
        assert "summary" in EBITDA_TREE_SCHEMA["properties"]
        assert "nodes" in EBITDA_TREE_SCHEMA["properties"]
        assert "revenue_estimate" in EBITDA_TREE_SCHEMA["properties"]
        assert "ebitda_estimate" in EBITDA_TREE_SCHEMA["properties"]

    def test_flat_schema_has_no_recursive_ref(self):
        """The flat schema should not contain any $ref — that's the whole point."""
        node_schema = EBITDA_TREE_SCHEMA["properties"]["nodes"]["items"]
        assert "$ref" not in str(node_schema)
        assert "$defs" not in EBITDA_TREE_SCHEMA

    def test_flat_node_schema_has_parent_id(self):
        node_schema = EBITDA_TREE_SCHEMA["properties"]["nodes"]["items"]
        assert "parent_id" in node_schema["properties"]
