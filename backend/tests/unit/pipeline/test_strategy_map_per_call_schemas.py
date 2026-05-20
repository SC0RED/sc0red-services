"""Per-call schema ↔ Pydantic-model alignment tests.

The decomposed strategy-map pipeline emits 19 per-call AI responses, each
validated against a narrow JSON Schema under
``backend/src/pipeline/prompts/strategy_map/schemas/per_call/``. The
assembled output is then validated by the strict ``StrategyMap`` Pydantic
model. These two contracts must stay in lockstep:

- If a Pydantic field is renamed, retyped, or has its enum tightened, the
  matching per-call schema must update too.
- If a per-call schema adds or removes a required property, the Pydantic
  model must match (or the assembly step explicitly fills the gap).

This file asserts that alignment for the four objective-detail schemas
that map 1:1 onto Pydantic ``Objective`` models (financial / customer /
internal / capacity). Schemas that don't have a clean Pydantic-subset
mapping (titles arrays, theme lists, arrow yes/no, value-proposition
facets) are covered by the strict-mode tests in
``test_strategy_map_schema_strict_mode.py``.

Strict-mode invariants (``additionalProperties: false``, every property
required) are already asserted there for every schema; this file adds
the *type-level* alignment check for the four detail schemas.
"""

from __future__ import annotations

import types
import typing
from typing import Any, Literal, get_args, get_origin

import pytest
from pydantic import BaseModel

from src.models.model_strategy_map import (
    CapacityObjective,
    CustomerObjective,
    FinancialObjective,
    InternalProcessObjective,
)
from src.pipeline.pipeline_steps._strategy_map_corpus import load_per_call_schema

# Schemas that correspond 1:1 to a Pydantic Objective model.
# Each entry: (schema-name, model, excluded-fields).
# - ``id`` is assigned by ``_strategy_map_assembly.py`` from title-list order.
# - ``title`` is provided as INPUT to the Round-2 prompt, not re-emitted.
# - ``linked_opportunity_indices`` is intentionally absent from the
#   AI-facing per-call schema. The Phase 1a slice of
#   ``redesign-analysis-visuals`` ships only the data shape on the
#   Pydantic model — Pydantic supplies the empty-list default during
#   assembly so the field is well-formed on every objective. Phase 1b
#   will add the per-call schema entry + the prompt instruction that
#   populates the field.
_OBJECTIVE_EXCLUDED = {"id", "title", "linked_opportunity_indices"}
_DETAIL_SCHEMA_MAPPINGS: list[tuple[str, type[BaseModel], set[str]]] = [
    ("financial_objective_detail", FinancialObjective, _OBJECTIVE_EXCLUDED),
    ("customer_objective_detail", CustomerObjective, _OBJECTIVE_EXCLUDED),
    ("internal_objective_detail", InternalProcessObjective, _OBJECTIVE_EXCLUDED),
    ("capacity_objective_detail", CapacityObjective, _OBJECTIVE_EXCLUDED),
]


def _expected_pydantic_keys(model: type[BaseModel], excluded: set[str]) -> set[str]:
    """Return the set of Pydantic field names the per-call schema is expected to cover."""
    return set(model.model_fields.keys()) - excluded


def _json_types_for_annotation(annotation: Any) -> set[str]:
    """Map a Pydantic field annotation to the JSON-Schema type strings it permits.

    Handles the cases the strategy-map detail schemas actually use:
    - ``str`` → ``{"string"}``
    - ``str | None`` → ``{"string", "null"}``
    - ``Literal[...]`` → ``{"string"}`` (Literal enums of strings)
    - subclasses of ``str`` (e.g. ``ConfidenceMarker``) → ``{"string"}``
    """
    origin = get_origin(annotation)
    # PEP-604 ``str | None`` → ``types.UnionType`` (Python 3.10+).
    # Legacy ``Union[str, None]`` → ``typing.Union``. Handle both.
    if origin is typing.Union or origin is types.UnionType:
        json_types: set[str] = set()
        for arg in get_args(annotation):
            json_types.update(_json_types_for_annotation(arg))
        return json_types
    if origin is Literal:
        # Literal of strings → "string" in JSON Schema.
        if all(isinstance(value, str) for value in get_args(annotation)):
            return {"string"}
        raise AssertionError(
            f"Non-string Literal not handled by this helper: {annotation!r}"
        )
    if annotation is type(None):
        return {"null"}
    if annotation is str or (isinstance(annotation, type) and issubclass(annotation, str)):
        return {"string"}
    raise AssertionError(
        f"Annotation {annotation!r} not handled — extend _json_types_for_annotation "
        f"if a new Pydantic field type is added to a detail schema."
    )


def _literal_values(annotation: Any) -> set[str] | None:
    """Return the set of Literal values if the annotation is a Literal of strings, else None."""
    origin = get_origin(annotation)
    if origin is Literal and all(isinstance(value, str) for value in get_args(annotation)):
        return set(get_args(annotation))
    # Handle Literal wrapped in Union with None (either ``Union`` or PEP-604 form).
    if origin is typing.Union or origin is types.UnionType:
        for arg in get_args(annotation):
            inner = _literal_values(arg)
            if inner is not None:
                return inner
    return None


def _schema_property_types(node: dict[str, Any]) -> set[str]:
    """Normalise a schema property's ``type`` into a set of JSON-Schema type strings."""
    raw = node.get("type")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return set(raw)
    if "enum" in node:
        # Enums in our schemas are always strings.
        return {"string"}
    raise AssertionError(f"Property has no ``type`` or ``enum``: {node!r}")


class TestPerCallSchemaPydanticAlignment:
    """Per-call detail schema ↔ Pydantic model alignment.

    Adding a field to a Pydantic Objective without updating the matching
    schema (or vice versa) will trip ``test_required_keys_match`` or
    ``test_property_types_match``.
    """

    @pytest.mark.parametrize("name, model, excluded", _DETAIL_SCHEMA_MAPPINGS)
    def test_required_keys_match(
        self, name: str, model: type[BaseModel], excluded: set[str]
    ) -> None:
        """Schema's ``required`` set MUST equal Pydantic field names minus excluded."""
        schema = load_per_call_schema(name)
        schema_required = set(schema.get("required", []))
        expected = _expected_pydantic_keys(model, excluded)
        assert schema_required == expected, (
            f"{name}.json required={sorted(schema_required)} but "
            f"{model.__name__} minus {sorted(excluded)} expects {sorted(expected)}. "
            "Update the schema or the model so they stay in lockstep."
        )

    @pytest.mark.parametrize("name, model, excluded", _DETAIL_SCHEMA_MAPPINGS)
    def test_property_keys_match(
        self, name: str, model: type[BaseModel], excluded: set[str]
    ) -> None:
        """Schema's ``properties`` keys MUST equal Pydantic field names minus excluded."""
        schema = load_per_call_schema(name)
        schema_props = set(schema["properties"].keys())
        expected = _expected_pydantic_keys(model, excluded)
        assert schema_props == expected, (
            f"{name}.json properties={sorted(schema_props)} but "
            f"{model.__name__} minus {sorted(excluded)} expects {sorted(expected)}."
        )

    @pytest.mark.parametrize("name, model, excluded", _DETAIL_SCHEMA_MAPPINGS)
    def test_property_types_match(
        self, name: str, model: type[BaseModel], excluded: set[str]
    ) -> None:
        """Each schema property's JSON-Schema type MUST cover the Pydantic field's annotation.

        Concretely: the set of JSON-Schema types declared for the property
        is exactly the set permitted by the Pydantic annotation (``str`` →
        ``{string}``, ``str | None`` → ``{string, null}``, ``Literal[...]``
        of strings → ``{string}``).
        """
        schema = load_per_call_schema(name)
        violations: list[str] = []
        for field_name, field_info in model.model_fields.items():
            if field_name in excluded:
                continue
            property_node = schema["properties"][field_name]
            actual_types = _schema_property_types(property_node)
            expected_types = _json_types_for_annotation(field_info.annotation)
            if actual_types != expected_types:
                violations.append(
                    f"{field_name}: schema declares {sorted(actual_types)}, "
                    f"Pydantic annotation {field_info.annotation!r} "
                    f"expects {sorted(expected_types)}"
                )
        assert not violations, f"{name}.json type mismatch:\n  " + "\n  ".join(violations)

    @pytest.mark.parametrize("name, model, excluded", _DETAIL_SCHEMA_MAPPINGS)
    def test_enum_values_match(
        self, name: str, model: type[BaseModel], excluded: set[str]
    ) -> None:
        """For each Literal-typed Pydantic field, the schema's ``enum`` MUST list the same values.

        Tightening a Literal (e.g. removing ``"medium"`` from ``ConfidenceMarker``)
        without tightening the schema enum (or vice versa) trips here.
        """
        schema = load_per_call_schema(name)
        violations: list[str] = []
        for field_name, field_info in model.model_fields.items():
            if field_name in excluded:
                continue
            literal_values = _literal_values(field_info.annotation)
            if literal_values is None:
                continue
            property_node = schema["properties"][field_name]
            schema_enum = set(property_node.get("enum", []))
            if schema_enum != literal_values:
                violations.append(
                    f"{field_name}: schema enum={sorted(schema_enum)}, "
                    f"Pydantic Literal={sorted(literal_values)}"
                )
        assert not violations, f"{name}.json enum mismatch:\n  " + "\n  ".join(violations)
