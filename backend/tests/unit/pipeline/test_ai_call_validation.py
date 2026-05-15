"""Tests for ``run_structured_ai_call``'s per-call boundary validator.

The validator (added 2026-05-15 for ``optimize-strategy-map-latency``
P3.2.2) runs ``jsonschema.validate(response.content, schema)`` after every
structured AI call. OpenAI's structured-output mode already enforces the
schema, so this is a defensive fast-fail guard: a malformed response trips
at the call boundary (with the call's ``label`` for triage) instead of
propagating to assembly and surfacing as a confusing Pydantic error
several steps later.

These tests pin the contract: valid responses pass through unchanged,
malformed responses raise ``jsonschema.ValidationError`` and the error
is logged with the call label + step name.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import jsonschema
import pytest

from src.pipeline.pipeline_steps.ai_call import run_structured_ai_call


def _build_ai_factory(response_content: dict[str, Any]) -> MagicMock:
    """Build a MagicMock ``AIClientFactory`` whose client returns ``response_content``."""
    factory = MagicMock()
    client = factory.get_client.return_value
    client.model = "gpt-test"
    response = MagicMock()
    response.content = response_content
    response.metadata = {"input_tokens": 100, "output_tokens": 50}
    client.query_structured.return_value = response
    return factory


@pytest.fixture
def detail_schema() -> dict[str, Any]:
    """A representative per-call schema (financial_objective_detail shape)."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["definition", "category", "confidence", "rationale_source"],
        "additionalProperties": False,
        "properties": {
            "definition": {"type": "string", "minLength": 50, "maxLength": 1200},
            "category": {"type": "string", "enum": ["revenue_growth", "productivity"]},
            "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
            "rationale_source": {"type": ["string", "null"], "maxLength": 400},
        },
    }


class TestRunStructuredAICallValidation:
    """Boundary-validation behaviour of ``run_structured_ai_call``."""

    def test_valid_response_passes_through_unchanged(
        self, detail_schema: dict[str, Any]
    ) -> None:
        """A response conforming to the schema is returned unchanged."""
        valid_response = {
            "definition": (
                "Grow recurring SaaS revenue by expanding the enterprise "
                "tier into 3 new vertical segments within 12 months."
            ),
            "category": "revenue_growth",
            "confidence": "HIGH",
            "rationale_source": "Customer cohort analysis Q2 2025",
        }
        factory = _build_ai_factory(valid_response)
        label, content, elapsed = run_structured_ai_call(
            ai_client_factory=factory,
            user_prompt="elaborate on objective F1",
            schema=detail_schema,
            system_prompt="strategy-map system",
            label="detail_financial_F1",
            step_name="GenerateStrategyMap",
        )
        assert label == "detail_financial_F1"
        assert content == valid_response
        assert elapsed >= 0.0

    def test_valid_response_with_null_nullable_field_passes_through(
        self, detail_schema: dict[str, Any]
    ) -> None:
        """A nullable field set to ``null`` passes the validator.

        Guards against an accidental tightening of ``rationale_source``'s
        type from ``["string", "null"]`` to ``"string"`` — that change
        would trip this test even though the field is in ``required``.
        """
        valid_response_with_null = {
            "definition": (
                "Grow recurring SaaS revenue by expanding the enterprise "
                "tier into 3 new vertical segments within 12 months."
            ),
            "category": "revenue_growth",
            "confidence": "HIGH",
            "rationale_source": None,
        }
        factory = _build_ai_factory(valid_response_with_null)
        label, content, _ = run_structured_ai_call(
            ai_client_factory=factory,
            user_prompt="elaborate on objective F1",
            schema=detail_schema,
            system_prompt="strategy-map system",
            label="detail_financial_F1",
            step_name="GenerateStrategyMap",
        )
        assert label == "detail_financial_F1"
        assert content["rationale_source"] is None

    def test_response_with_missing_required_field_raises(
        self, detail_schema: dict[str, Any]
    ) -> None:
        """Missing a required field trips the boundary validator."""
        malformed = {
            "definition": (
                "Grow recurring SaaS revenue by expanding the enterprise tier "
                "into 3 new vertical segments within 12 months."
            ),
            # ``category`` missing
            "confidence": "HIGH",
            "rationale_source": None,
        }
        factory = _build_ai_factory(malformed)
        with pytest.raises(jsonschema.ValidationError):
            run_structured_ai_call(
                ai_client_factory=factory,
                user_prompt="elaborate on objective F1",
                schema=detail_schema,
                system_prompt="strategy-map system",
                label="detail_financial_F1",
                step_name="GenerateStrategyMap",
            )

    def test_response_with_extra_field_raises(
        self, detail_schema: dict[str, Any]
    ) -> None:
        """``additionalProperties: false`` is enforced — extra fields trip validation."""
        malformed = {
            "definition": (
                "Grow recurring SaaS revenue by expanding the enterprise tier "
                "into 3 new vertical segments within 12 months."
            ),
            "category": "revenue_growth",
            "confidence": "HIGH",
            "rationale_source": None,
            "id": "F1",  # extra field — should be assigned by assembly, not emitted
        }
        factory = _build_ai_factory(malformed)
        with pytest.raises(jsonschema.ValidationError):
            run_structured_ai_call(
                ai_client_factory=factory,
                user_prompt="elaborate on objective F1",
                schema=detail_schema,
                system_prompt="strategy-map system",
                label="detail_financial_F1",
                step_name="GenerateStrategyMap",
            )

    def test_response_with_wrong_enum_value_raises(
        self, detail_schema: dict[str, Any]
    ) -> None:
        """An enum value outside the allowed set trips validation."""
        malformed = {
            "definition": (
                "Grow recurring SaaS revenue by expanding the enterprise tier "
                "into 3 new vertical segments within 12 months."
            ),
            "category": "revenue_growth",
            "confidence": "VERY_HIGH",  # not in {HIGH, MEDIUM, LOW}
            "rationale_source": None,
        }
        factory = _build_ai_factory(malformed)
        with pytest.raises(jsonschema.ValidationError):
            run_structured_ai_call(
                ai_client_factory=factory,
                user_prompt="elaborate on objective F1",
                schema=detail_schema,
                system_prompt="strategy-map system",
                label="detail_financial_F1",
                step_name="GenerateStrategyMap",
            )

    def test_validation_error_is_logged_with_label_and_step_name(
        self,
        detail_schema: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The validator's error log includes the label + step name for triage."""
        malformed = {
            "definition": "too short",  # violates minLength=50 — but also invalid
            "category": "revenue_growth",
            "confidence": "HIGH",
            "rationale_source": None,
        }
        factory = _build_ai_factory(malformed)
        with caplog.at_level(logging.ERROR), pytest.raises(jsonschema.ValidationError):
            run_structured_ai_call(
                ai_client_factory=factory,
                user_prompt="elaborate on objective F1",
                schema=detail_schema,
                system_prompt="strategy-map system",
                label="detail_financial_F1",
                step_name="GenerateStrategyMap",
            )
        log_text = " ".join(record.getMessage() for record in caplog.records)
        assert "detail_financial_F1" in log_text
        assert "GenerateStrategyMap" in log_text
        assert "per-call schema validation" in log_text
