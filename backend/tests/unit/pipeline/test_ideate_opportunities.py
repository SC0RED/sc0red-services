"""Tests for ideate_opportunities — schema validation and prompt building."""

from src.pipeline.pipeline_steps.ideate_opportunities import (
    IDEATION_SCHEMA,
    IDEATION_SYSTEM_PROMPT,
    build_ideation_prompt,
    get_all_ideation_categories,
)


class TestIdeationSchema:
    def test_required_fields(self):
        assert set(IDEATION_SCHEMA["required"]) == {
            "title",
            "description",
            "value_lever",
            "strategic_category",
            "impact_rating",
        }

    def test_no_extra_fields(self):
        assert IDEATION_SCHEMA["additionalProperties"] is False

    def test_impact_rating_enum(self):
        props = IDEATION_SCHEMA["properties"]
        assert props["impact_rating"]["enum"] == ["High", "Medium", "Low"]

    def test_value_lever_enum(self):
        props = IDEATION_SCHEMA["properties"]
        assert props["value_lever"]["enum"] == ["Revenue Side", "Cost Side", "Both"]

    def test_schema_does_not_have_implementation_steps(self):
        """Routing key: ideation has impact_rating but NOT implementation_steps."""
        assert "implementation_steps" not in IDEATION_SCHEMA["properties"]


class TestIdeationSystemPrompt:
    def test_is_non_empty_string(self):
        assert isinstance(IDEATION_SYSTEM_PROMPT, str)
        assert len(IDEATION_SYSTEM_PROMPT) > 50

    def test_mentions_risk_category(self):
        assert "risk category" in IDEATION_SYSTEM_PROMPT.lower()


class TestBuildIdeationPrompt:
    def test_includes_scraped_text(self):
        prompt = build_ideation_prompt(
            scraped_text="Acme Corp website content",
            url="https://acme.com",
            category_id="competitive_displacement",
            category_name="Competitive Displacement",
            category_description="Risk of AI-native competitors",
        )
        assert "Acme Corp website content" in prompt

    def test_includes_url(self):
        prompt = build_ideation_prompt(
            scraped_text="content",
            url="https://acme.com",
            category_id="competitive_displacement",
            category_name="Competitive Displacement",
            category_description="Risk of AI-native competitors",
        )
        assert "https://acme.com" in prompt

    def test_includes_category(self):
        prompt = build_ideation_prompt(
            scraped_text="content",
            url="https://acme.com",
            category_id="talent_workforce",
            category_name="Talent & Workforce",
            category_description="Risk that AI automates key workforce functions",
        )
        assert "talent_workforce" in prompt
        assert "Talent & Workforce" in prompt

    def test_includes_documents_when_provided(self):
        prompt = build_ideation_prompt(
            scraped_text="content",
            url="https://acme.com",
            category_id="data_ip",
            category_name="Data & IP",
            category_description="Risk to data",
            document_text="Investment memo: Revenue is $50M annually.",
        )
        assert "SUPPLEMENTARY DOCUMENTS" in prompt
        assert "Investment memo" in prompt

    def test_excludes_documents_when_none(self):
        prompt = build_ideation_prompt(
            scraped_text="content",
            url="https://acme.com",
            category_id="data_ip",
            category_name="Data & IP",
            category_description="Risk to data",
            document_text=None,
        )
        assert "SUPPLEMENTARY DOCUMENTS" not in prompt

    def test_includes_strategic_categories(self):
        prompt = build_ideation_prompt(
            scraped_text="content",
            url="https://acme.com",
            category_id="data_ip",
            category_name="Data & IP",
            category_description="Risk to data",
        )
        assert "Competitive Moat" in prompt
        assert "Revenue Capture" in prompt


class TestGetAllIdeationCategories:
    def test_returns_eight_categories(self):
        categories = get_all_ideation_categories()
        assert len(categories) == 8

    def test_each_has_required_keys(self):
        for category in get_all_ideation_categories():
            assert "id" in category
            assert "name" in category
            assert "description" in category

    def test_includes_all_risk_scopes(self):
        ids = {category["id"] for category in get_all_ideation_categories()}
        assert "competitive_displacement" in ids
        assert "data_ip" in ids
