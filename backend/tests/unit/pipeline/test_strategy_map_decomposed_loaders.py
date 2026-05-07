"""Tests for the per-call schema + decomposed-template loaders.

Validates that all 9 per-call schemas and 10 decomposed templates added
in `optimize-strategy-map-latency` Phase 1 actually load. Acts as a
guard against accidental rename / move / typo in the corpus filenames
that the orchestration module relies on.
"""

from __future__ import annotations

import jsonschema
import pytest

from src.pipeline.pipeline_steps._strategy_map_corpus import (
    load_decomposed_template,
    load_per_call_schema,
)


# Names the orchestration module references at runtime. If any of these
# stop loading the decomposed path is broken — pin them.
_PER_CALL_SCHEMAS = [
    "financial_titles",
    "customer_titles",
    "capacity_titles",
    "internal_themes",
    "internal_titles_per_theme",
    "financial_objective_detail",
    "customer_objective_detail",
    "internal_objective_detail",
    "capacity_objective_detail",
    "core_values",
]

_DECOMPOSED_TEMPLATES = [
    "round1_titles_financial",
    "round1_titles_customer",
    "round1_titles_capacity",
    "round1_themes_internal",
    "round1_core_values",
    "round2_detail_financial",
    "round2_detail_customer",
    "round2_detail_capacity",
    "round2_titles_internal_per_theme",
    "round3_detail_internal",
]


@pytest.mark.parametrize("name", _PER_CALL_SCHEMAS)
def test_per_call_schema_loads_and_is_valid_json_schema(name: str) -> None:
    """Each per-call schema loads + is itself a valid JSON Schema (Draft-7)."""
    schema = load_per_call_schema(name)
    # `Draft7Validator` validates the schema-of-schemas (raises if the
    # dict isn't a legal JSON Schema). Catches syntax errors early.
    jsonschema.Draft7Validator.check_schema(schema)
    # All Phase 1 per-call schemas use object root with explicit fields.
    assert schema["type"] == "object"
    assert "properties" in schema


@pytest.mark.parametrize("name", _DECOMPOSED_TEMPLATES)
def test_decomposed_template_loads(name: str) -> None:
    """Each decomposed template loads from `templates/decomposed/{name}.md`."""
    template = load_decomposed_template(name)
    assert isinstance(template, str)
    assert len(template) > 0
    # Sanity: every decomposed template includes the placeholder marker
    # for `{company_name}` (all of them reference the company in inputs).
    assert "{company_name}" in template


def test_detail_schemas_omit_id_field() -> None:
    """Per Decision §2: detail schemas MUST exclude `id` (assembly assigns it).

    Pin this for every Round 2 / Round 3 detail schema. A regression where
    a future contributor adds `id` back to a detail schema would silently
    cause double-ID assignment (the AI would emit one, the assembly would
    emit another) and Pydantic validation would fail with a confusing
    error. Catch it at the schema layer.
    """
    detail_schemas = [
        "financial_objective_detail",
        "customer_objective_detail",
        "internal_objective_detail",
        "capacity_objective_detail",
    ]
    for name in detail_schemas:
        schema = load_per_call_schema(name)
        properties = schema["properties"]
        assert "id" not in properties, (
            f"{name}.json must NOT request an `id` field — assembly assigns "
            f"positional IDs from title-list order. See Decision §2."
        )
        assert "title" not in properties, (
            f"{name}.json must NOT request a `title` field — title is "
            f"provided to the call as input from Round 1's output."
        )


def test_title_list_schemas_use_titles_array() -> None:
    """Round 1 title schemas all use `{titles: string[]}` shape (except capacity)."""
    title_list_schemas = [
        "financial_titles",
        "customer_titles",
        "internal_titles_per_theme",
    ]
    for name in title_list_schemas:
        schema = load_per_call_schema(name)
        assert "titles" in schema["properties"]
        assert schema["properties"]["titles"]["type"] == "array"


def test_capacity_titles_schema_uses_fixed_bucket_keys() -> None:
    """Capacity Round 1 returns one title per fixed bucket (no `titles` array)."""
    schema = load_per_call_schema("capacity_titles")
    properties = schema["properties"]
    assert {"people", "technology", "culture"}.issubset(properties.keys())
