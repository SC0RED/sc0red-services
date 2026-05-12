"""Regression tests for the strategy-map JSON schema's OpenAI strict-mode shape.

OpenAI's structured-output mode (`response_format` with a JSON schema)
runs in *strict* mode for the `gpt-5.x` family. Strict mode imposes
two invariants on every object schema:

1. Every key declared in ``properties`` MUST also appear in
   ``required``. There is no concept of "optional present" on the
   wire — fields are either required (and produced) or absent.
2. ``additionalProperties`` MUST be ``false``.

Optional semantics are achieved by declaring the type as nullable
(``["string", "null"]``) and letting the model emit ``null`` when
there is no value. The receiving Pydantic model then accepts
``str | None``.

Production incident (2026-05-04, against `gpt-5.1`):

    Invalid schema for response_format 'structured_response': In
    context=(), 'required' is required to be supplied and to be an
    array including every key in properties. Missing 'rationale_source'.

This test walks the schema tree and asserts the invariants on every
nested object. A future edit that adds a property to ``properties``
without adding it to ``required`` (or that sets
``additionalProperties: true``) will fail here, not in production.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.pipeline.pipeline_steps._strategy_map_corpus import (
    load_per_call_schema,
    load_schema,
)

# Every per-call schema used by the decomposed paths (Phase 1 + Phase 2).
# Kept in sync with ``test_strategy_map_decomposed_loaders.py``'s
# ``_PER_CALL_SCHEMAS`` list; both lists must contain every schema the
# orchestration loads at runtime.
_PER_CALL_SCHEMAS = [
    # Phase 1 (optimize-strategy-map-latency)
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
    # Phase 2 (decompose-strategy-map-synthesis)
    "vision_text",
    "mission_text",
    "synth_yesno",
    "vp_primary",
    "vp_secondary",
    "vp_exemplar",
    "vp_rationale",
    "arrow_yesno",
    "arrows_priorities",
    "arrows_gaps",
]


def _is_object_schema(node: dict[str, Any]) -> bool:
    """Return True if `node` is an object-type schema with a properties block.

    Handles both the explicit-type form (``{"type": "object", ...}``) and
    the implicit form where a node has ``properties`` without an explicit
    type. Either form is treated by JSON-schema as an object schema.
    """
    if "properties" not in node:
        return False
    type_value = node.get("type")
    if type_value is None:
        return True
    if type_value == "object":
        return True
    return isinstance(type_value, list) and "object" in type_value


def _walk_object_schemas(node: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
    """Yield every object-shaped schema in the tree along with a JSON-pointer-ish path.

    Walks ``properties``, ``items``, ``definitions``, and ``$defs``.
    ``$ref`` nodes are NOT followed (the referenced definition is also
    walked when we hit ``definitions``/``$defs``).
    """
    found: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(node, dict):
        return found

    if _is_object_schema(node):
        found.append((path or "/", node))

    for key, child in node.get("properties", {}).items():
        found.extend(_walk_object_schemas(child, f"{path}/properties/{key}"))

    items = node.get("items")
    if isinstance(items, dict):
        found.extend(_walk_object_schemas(items, f"{path}/items"))
    elif isinstance(items, list):
        for index, item in enumerate(items):
            found.extend(_walk_object_schemas(item, f"{path}/items/{index}"))

    for definitions_key in ("definitions", "$defs"):
        for key, child in node.get(definitions_key, {}).items():
            found.extend(_walk_object_schemas(child, f"{path}/{definitions_key}/{key}"))

    return found


class TestStrategyMapSchemaStrictMode:
    @pytest.fixture(scope="class")
    def schema(self) -> dict[str, Any]:
        return load_schema()

    def test_every_property_is_in_required(self, schema: dict[str, Any]) -> None:
        """Strict-mode invariant 1: every key in `properties` must be in `required`."""
        violations: list[str] = []
        for path, node in _walk_object_schemas(schema):
            properties = set(node["properties"].keys())
            required = set(node.get("required", []))
            missing = sorted(properties - required)
            if missing:
                violations.append(f"{path}: properties not in required = {missing}")
        assert not violations, "OpenAI strict-mode violations found:\n  " + "\n  ".join(violations)

    def test_additional_properties_is_false(self, schema: dict[str, Any]) -> None:
        """Strict-mode invariant 2: every object schema must set `additionalProperties: false`."""
        violations: list[str] = []
        for path, node in _walk_object_schemas(schema):
            if node.get("additionalProperties") is not False:
                violations.append(f"{path}: additionalProperties is not false")
        assert not violations, "OpenAI strict-mode violations found:\n  " + "\n  ".join(violations)

    def test_known_nullable_optional_fields_are_nullable(self, schema: dict[str, Any]) -> None:
        """Locks in the *intent*: optional fields use nullable types, not omission.

        These fields existed as "optional via missing-from-required" before
        the strict-mode fix. They are now required-but-nullable. If a
        future edit reverts them to non-nullable, this asserts the
        regression visibly (rather than just failing the strict-mode
        invariant tests with a less specific error).
        """
        nullable_paths = (
            ("/properties/valueProposition/properties/exemplar_company", "string"),
            ("/definitions/financialObjective/properties/rationale_source", "string"),
            ("/definitions/customerObjective/properties/rationale_source", "string"),
            ("/definitions/internalProcessObjective/properties/rationale_source", "string"),
            ("/definitions/capacityObjective/properties/rationale_source", "string"),
        )
        for path, expected_inner_type in nullable_paths:
            node = self._resolve(schema, path)
            type_field = node.get("type")
            assert isinstance(type_field, list), (
                f"{path}: expected nullable type list, got {type_field!r}"
            )
            assert "null" in type_field, f"{path}: missing 'null' in type list ({type_field})"
            assert expected_inner_type in type_field, (
                f"{path}: missing {expected_inner_type!r} in type list ({type_field})"
            )

    @staticmethod
    def _resolve(schema: dict[str, Any], path: str) -> dict[str, Any]:
        """Walk a JSON-pointer-ish path (no escaping needed for our keys)."""
        node: Any = schema
        for segment in path.strip("/").split("/"):
            node = node[segment]
        return node


class TestPerCallSchemaStrictMode:
    """Strict-mode invariants applied to every per-call decomposed schema.

    Production incident (2026-05-11, against `gpt-5.1`):

        Invalid schema for response_format 'structured_response': In
        context=('properties', 'whatsMissing', 'items'), 'required' is
        required to be supplied and to be an array including every key
        in properties. Missing 'relatedObjectiveIds'.

    The strategy_map_output.json strict-mode tests above did not catch
    this because the decomposed pipeline does NOT send the assembled
    schema — it sends 30+ per-call schemas, each of which must
    independently comply with OpenAI strict mode. This test class
    parametrises every per-call schema and applies the same invariants.
    """

    @pytest.mark.parametrize("name", _PER_CALL_SCHEMAS)
    def test_every_property_is_in_required(self, name: str) -> None:
        """Every key in ``properties`` MUST appear in ``required``."""
        schema = load_per_call_schema(name)
        violations: list[str] = []
        for path, node in _walk_object_schemas(schema):
            properties = set(node["properties"].keys())
            required = set(node.get("required", []))
            missing = sorted(properties - required)
            if missing:
                violations.append(f"{name}{path}: properties not in required = {missing}")
        assert not violations, (
            "OpenAI strict-mode violations in per-call schema:\n  " + "\n  ".join(violations)
        )

    @pytest.mark.parametrize("name", _PER_CALL_SCHEMAS)
    def test_additional_properties_is_false(self, name: str) -> None:
        """Every object schema MUST set ``additionalProperties: false``."""
        schema = load_per_call_schema(name)
        violations: list[str] = []
        for path, node in _walk_object_schemas(schema):
            if node.get("additionalProperties") is not False:
                violations.append(f"{name}{path}: additionalProperties is not false")
        assert not violations, (
            "OpenAI strict-mode violations in per-call schema:\n  " + "\n  ".join(violations)
        )
