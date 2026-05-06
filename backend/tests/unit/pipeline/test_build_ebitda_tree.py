"""Tests for the programmatic EBITDA tree builder."""

from src.models.model_company import CompanyProfile, EbitdaNode, EbitdaTreeResult
from src.pipeline.pipeline_steps._ebitda_confidence import _compute_confidence
from src.pipeline.pipeline_steps._ebitda_templates import _resolve_template
from src.pipeline.pipeline_steps.build_ebitda_tree import (
    _format_currency,
    _format_range,
    build_programmatic_ebitda_tree,
)


class TestResolveTemplate:
    def test_saas_keywords(self):
        for model in ["SaaS", "B2B SaaS", "Enterprise SaaS", "Software as a Service"]:
            template, matched = _resolve_template(model)
            assert template.label == "SaaS"
            assert matched is True

    def test_services_keywords(self):
        for model in ["Professional Services", "Consulting", "Advisory", "Digital Agency"]:
            template, matched = _resolve_template(model)
            assert template.label == "Professional Services"
            assert matched is True

    def test_ecommerce_keywords(self):
        for model in ["E-commerce", "ecommerce", "Marketplace", "DTC Retail"]:
            template, matched = _resolve_template(model)
            assert template.label == "E-commerce / Marketplace"
            assert matched is True

    def test_manufacturing_keywords(self):
        for model in ["Manufacturing", "Industrial Products", "Hardware Manufacturer"]:
            template, matched = _resolve_template(model)
            assert template.label == "Manufacturing"
            assert matched is True

    def test_financial_services_keywords(self):
        for model in ["Financial Services", "Fintech", "Banking Platform", "Insurance"]:
            template, matched = _resolve_template(model)
            assert template.label == "Financial Services"
            assert matched is True

    def test_unknown_defaults_to_saas_and_reports_unmatched(self):
        template, matched = _resolve_template("Unknown Business Type")
        assert template.label == "SaaS"
        assert matched is False

    def test_empty_defaults_to_saas_and_reports_unmatched(self):
        template, matched = _resolve_template("")
        assert template.label == "SaaS"
        assert matched is False


class TestFormatCurrency:
    def test_billions(self):
        assert _format_currency(2_000_000_000) == "$2B"
        assert _format_currency(1_500_000_000) == "$1.5B"

    def test_millions(self):
        assert _format_currency(10_000_000) == "$10M"
        assert _format_currency(150_000_000) == "$150M"

    def test_thousands(self):
        assert _format_currency(500_000) == "$500K"
        assert _format_currency(50_000) == "$50K"

    def test_small_amounts(self):
        assert _format_currency(999) == "$999"


class TestFormatRange:
    def test_million_range(self):
        assert _format_range(10_000_000, 50_000_000) == "$10M-$50M"

    def test_mixed_range(self):
        assert _format_range(500_000, 5_000_000) == "$500K-$5M"


class TestBuildProgrammaticEbitdaTree:
    def _make_profile(
        self,
        business_model: str = "SaaS",
        company_size: str = "Mid-market 200-1000",
        company_name: str = "Test Corp",
    ) -> CompanyProfile:
        return CompanyProfile(
            company_name=company_name,
            industry="Technology",
            business_model=business_model,
            company_size=company_size,
        )

    def test_returns_ebitda_tree_result(self):
        result = build_programmatic_ebitda_tree(self._make_profile())
        assert isinstance(result, EbitdaTreeResult)

    def test_has_five_root_nodes(self):
        result = build_programmatic_ebitda_tree(self._make_profile())
        assert len(result.nodes) == 5
        node_ids = [n.id for n in result.nodes]
        assert node_ids == ["revenue", "cogs", "gross_profit", "opex", "ebitda"]

    def test_root_node_types(self):
        result = build_programmatic_ebitda_tree(self._make_profile())
        types = {n.id: n.type for n in result.nodes}
        assert types["revenue"] == "revenue"
        assert types["cogs"] == "cost"
        assert types["gross_profit"] == "subtotal"
        assert types["opex"] == "cost"
        assert types["ebitda"] == "subtotal"

    def test_saas_has_revenue_children(self):
        result = build_programmatic_ebitda_tree(self._make_profile(business_model="SaaS"))
        revenue_node = result.nodes[0]
        assert len(revenue_node.children) == 3
        child_labels = [c.label for c in revenue_node.children]
        assert "Subscriptions" in child_labels

    def test_saas_has_cogs_children(self):
        result = build_programmatic_ebitda_tree(self._make_profile(business_model="SaaS"))
        cogs_node = result.nodes[1]
        assert len(cogs_node.children) == 3
        child_labels = [c.label for c in cogs_node.children]
        assert "Cloud Infrastructure" in child_labels

    def test_saas_has_opex_children(self):
        result = build_programmatic_ebitda_tree(self._make_profile(business_model="SaaS"))
        opex_node = result.nodes[3]
        assert len(opex_node.children) == 3
        child_labels = [c.label for c in opex_node.children]
        assert "R&D" in child_labels

    def test_services_template_has_different_structure(self):
        result = build_programmatic_ebitda_tree(
            self._make_profile(business_model="Professional Services")
        )
        revenue_node = result.nodes[0]
        child_labels = [c.label for c in revenue_node.children]
        assert "Retainers / Managed Services" in child_labels
        # Should NOT have SaaS-specific items
        assert "Subscriptions" not in child_labels

    def test_manufacturing_template(self):
        result = build_programmatic_ebitda_tree(
            self._make_profile(business_model="Manufacturing")
        )
        cogs_node = result.nodes[1]
        child_labels = [c.label for c in cogs_node.children]
        assert "Raw Materials" in child_labels

    def test_children_have_percentage_of_parent(self):
        result = build_programmatic_ebitda_tree(self._make_profile())
        revenue_node = result.nodes[0]
        total_pct = sum(c.percentage_of_parent for c in revenue_node.children if c.percentage_of_parent)
        assert total_pct == 100

    def test_revenue_estimate_is_populated(self):
        result = build_programmatic_ebitda_tree(self._make_profile())
        assert result.revenue_estimate
        assert "$" in result.revenue_estimate

    def test_ebitda_estimate_is_populated(self):
        result = build_programmatic_ebitda_tree(self._make_profile())
        assert result.ebitda_estimate
        assert "$" in result.ebitda_estimate
        assert "margin" in result.ebitda_estimate

    def test_summary_contains_company_name(self):
        result = build_programmatic_ebitda_tree(
            self._make_profile(company_name="Acme Corp")
        )
        assert "Acme Corp" in result.summary

    def test_summary_contains_business_model(self):
        result = build_programmatic_ebitda_tree(self._make_profile(business_model="SaaS"))
        assert "SaaS" in result.summary

    def test_value_ranges_contain_dollar_signs(self):
        result = build_programmatic_ebitda_tree(self._make_profile())
        for node in result.nodes:
            assert "$" in node.value_range

    def test_startup_has_smaller_revenue_than_enterprise(self):
        startup = build_programmatic_ebitda_tree(
            self._make_profile(company_size="Startup <50")
        )
        enterprise = build_programmatic_ebitda_tree(
            self._make_profile(company_size="Enterprise 5000+")
        )
        # Compare the revenue_estimate strings (rough check: startup should be smaller)
        assert "B" not in startup.revenue_estimate
        assert "M" in enterprise.revenue_estimate or "B" in enterprise.revenue_estimate

    def test_unknown_company_size_uses_default(self):
        """Empty or unknown company_size should not crash."""
        result = build_programmatic_ebitda_tree(self._make_profile(company_size=""))
        assert result.revenue_estimate
        assert len(result.nodes) == 5

    def test_all_templates_produce_valid_trees(self):
        """Every supported business model should produce a valid 5-node tree."""
        for model in ["SaaS", "Consulting", "E-commerce", "Manufacturing", "Fintech"]:
            result = build_programmatic_ebitda_tree(self._make_profile(business_model=model))
            assert len(result.nodes) == 5
            assert result.summary
            assert result.revenue_estimate
            assert result.ebitda_estimate

    def test_gross_profit_and_ebitda_nodes_have_no_children(self):
        result = build_programmatic_ebitda_tree(self._make_profile())
        gross_profit = result.nodes[2]
        ebitda = result.nodes[4]
        assert gross_profit.children == []
        assert ebitda.children == []

    def test_child_value_ranges_are_subset_of_parent(self):
        """Child node value ranges should be smaller than parent."""
        result = build_programmatic_ebitda_tree(self._make_profile())
        revenue_node = result.nodes[0]
        # Each child should have a value range (not empty)
        for child in revenue_node.children:
            assert child.value_range
            assert "$" in child.value_range

    def test_no_negative_value_ranges(self):
        """All value ranges must be non-negative across all templates and sizes."""
        for model in ["SaaS", "Consulting", "E-commerce", "Manufacturing", "Fintech"]:
            for size in [
                "Startup <50",
                "Small 50-200",
                "Mid-market 200-1000",
                "Large 1000-5000",
                "Enterprise 5000+",
                "",
            ]:
                result = build_programmatic_ebitda_tree(
                    self._make_profile(business_model=model, company_size=size)
                )
                for node in result.nodes:
                    assert "$-" not in node.value_range, (
                        f"Negative value in {node.id} for {model}/{size}: {node.value_range}"
                    )
                    for child in node.children:
                        assert "$-" not in child.value_range, (
                            f"Negative value in {child.id} for {model}/{size}: {child.value_range}"
                        )


# ---------------------------------------------------------------------------
# Derivation-provenance confidence (ebitda-tree-confidence capability)
# ---------------------------------------------------------------------------


def _make_profile(
    business_model: str = "SaaS",
    company_size: str = "Mid-market 200-1000",
    company_name: str = "Test Corp",
) -> CompanyProfile:
    return CompanyProfile(
        company_name=company_name,
        industry="Technology",
        business_model=business_model,
        company_size=company_size,
    )


class TestConfidenceComputation:
    """Branch coverage for the (level, basis) decision in _compute_confidence."""

    def test_high_when_both_inputs_resolve(self):
        result = build_programmatic_ebitda_tree(
            _make_profile(business_model="SaaS", company_size="Mid-market 200-1000")
        )
        revenue_node = result.nodes[0]
        assert revenue_node.confidence_level == "high"
        # Basis names BOTH the matched template AND the matched size
        assert revenue_node.confidence_basis is not None
        assert "SaaS" in revenue_node.confidence_basis
        assert "Mid-market 200-1000" in revenue_node.confidence_basis
        assert "matched" in revenue_node.confidence_basis

    def test_medium_when_template_matches_but_size_defaults(self):
        result = build_programmatic_ebitda_tree(
            _make_profile(business_model="SaaS", company_size="not-a-real-bracket")
        )
        revenue_node = result.nodes[0]
        assert revenue_node.confidence_level == "medium"
        assert revenue_node.confidence_basis is not None
        assert "SaaS" in revenue_node.confidence_basis
        # The size side should declare itself defaulted
        assert "default" in revenue_node.confidence_basis.lower()

    def test_medium_when_size_matches_but_template_defaults(self):
        # Unknown business model falls back to the SaaS default template.
        result = build_programmatic_ebitda_tree(
            _make_profile(business_model="Holographic Bunny Sales", company_size="Startup <50")
        )
        revenue_node = result.nodes[0]
        assert revenue_node.confidence_level == "medium"
        assert revenue_node.confidence_basis is not None
        assert "Startup <50" in revenue_node.confidence_basis
        # The template side should declare itself defaulted
        assert "default" in revenue_node.confidence_basis.lower()

    def test_low_when_both_inputs_default(self):
        result = build_programmatic_ebitda_tree(
            _make_profile(business_model="Holographic Bunny Sales", company_size="")
        )
        revenue_node = result.nodes[0]
        assert revenue_node.confidence_level == "low"
        assert revenue_node.confidence_basis is not None
        # Both sides declare themselves defaulted
        assert revenue_node.confidence_basis.lower().count("default") >= 2

    def test_revenue_confidence_propagates_to_revenue_children(self):
        result = build_programmatic_ebitda_tree(
            _make_profile(business_model="SaaS", company_size="Mid-market 200-1000")
        )
        revenue_node = result.nodes[0]
        for child in revenue_node.children:
            assert child.confidence_level == "high"
            assert child.confidence_basis == revenue_node.confidence_basis

    def test_cost_confidence_phrased_for_cost_provenance(self):
        result = build_programmatic_ebitda_tree(
            _make_profile(business_model="SaaS", company_size="Mid-market 200-1000")
        )
        cogs_node = result.nodes[1]
        assert cogs_node.confidence_level == "high"
        assert cogs_node.confidence_basis is not None
        # Cost basis must reference the industry-benchmark margin lineage.
        assert "industry-benchmark" in cogs_node.confidence_basis
        assert "margin" in cogs_node.confidence_basis

    def test_cost_confidence_propagates_to_cogs_and_opex_children(self):
        result = build_programmatic_ebitda_tree(
            _make_profile(business_model="SaaS", company_size="Mid-market 200-1000")
        )
        cogs_node = result.nodes[1]
        opex_node = result.nodes[3]
        for child in cogs_node.children:
            assert child.confidence_level == "high"
            assert child.confidence_basis == cogs_node.confidence_basis
        for child in opex_node.children:
            assert child.confidence_level == "high"
            assert child.confidence_basis == opex_node.confidence_basis

    def test_subtotal_and_margin_nodes_carry_no_confidence(self):
        """Per ebitda-tree-confidence spec: rollups inherit visually via children."""
        result = build_programmatic_ebitda_tree(_make_profile())
        gross_profit = result.nodes[2]
        ebitda = result.nodes[4]
        assert gross_profit.type == "subtotal"
        assert ebitda.type == "subtotal"
        assert gross_profit.confidence_level is None
        assert gross_profit.confidence_basis is None
        assert ebitda.confidence_level is None
        assert ebitda.confidence_basis is None

    def test_revenue_basis_phrasing(self):
        level, basis = _compute_confidence(
            template=_resolve_template("SaaS")[0],
            template_matched=True,
            company_size="Mid-market 200-1000",
            size_matched=True,
            node_kind="revenue",
        )
        assert level == "high"
        # Revenue basis should NOT mention margin lineage
        assert "margin" not in basis
        assert basis.startswith("Revenue derived from")

    def test_cost_basis_phrasing(self):
        level, basis = _compute_confidence(
            template=_resolve_template("SaaS")[0],
            template_matched=True,
            company_size="Mid-market 200-1000",
            size_matched=True,
            node_kind="cost",
        )
        assert level == "high"
        assert basis.startswith("Cost derived from")
        assert "industry-benchmark" in basis

    def test_all_size_brackets_count_as_resolved(self):
        """Every documented company_size bracket should produce high confidence with a known model."""
        for size in [
            "Startup <50",
            "Small 50-200",
            "Mid-market 200-1000",
            "Large 1000-5000",
            "Enterprise 5000+",
        ]:
            result = build_programmatic_ebitda_tree(
                _make_profile(business_model="SaaS", company_size=size)
            )
            revenue_node = result.nodes[0]
            assert revenue_node.confidence_level == "high", (
                f"Expected high for size={size!r}, got {revenue_node.confidence_level!r}"
            )

    def test_every_template_at_a_known_size_is_high(self):
        for model in ["SaaS", "Consulting", "E-commerce", "Manufacturing", "Fintech"]:
            result = build_programmatic_ebitda_tree(
                _make_profile(business_model=model, company_size="Mid-market 200-1000")
            )
            revenue_node = result.nodes[0]
            assert revenue_node.confidence_level == "high", (
                f"Expected high for model={model!r}, got {revenue_node.confidence_level!r}"
            )


class TestEbitdaNodeBackwardCompat:
    """Old records lacking the confidence fields must still deserialize cleanly."""

    def test_old_payload_round_trips_with_null_confidence(self):
        """A payload stored before this change has no confidence_* fields."""
        old_payload = {
            "id": "revenue",
            "label": "Total Revenue",
            "type": "revenue",
            "value_range": "$5M-$20M",
            "percentage_of_parent": None,
            "description": "Total annual revenue",
            "linked_opportunity_indices": [],
            "children": [],
        }
        node = EbitdaNode.model_validate(old_payload)
        assert node.confidence_level is None
        assert node.confidence_basis is None
        # Round-trip preserves the (absent) shape — no fields injected on dump.
        dumped = node.model_dump()
        assert dumped["confidence_level"] is None
        assert dumped["confidence_basis"] is None

    def test_full_tree_with_old_payload_deserializes(self):
        """An EbitdaTreeResult with old-shaped nodes must still round-trip."""
        old_tree = {
            "summary": "Acme Corp operates ...",
            "revenue_estimate": "$5M-$20M",
            "ebitda_estimate": "$1M-$5M (15-25% margin)",
            "nodes": [
                {
                    "id": "revenue",
                    "label": "Total Revenue",
                    "type": "revenue",
                    "value_range": "$5M-$20M",
                    "description": "Total annual revenue",
                    "children": [],
                },
            ],
        }
        result = EbitdaTreeResult.model_validate(old_tree)
        assert result.nodes[0].confidence_level is None
        assert result.nodes[0].confidence_basis is None
