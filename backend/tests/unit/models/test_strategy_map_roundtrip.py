"""Round-trip serialisation tests for the StrategyMap pydantic model.

Verifies that a StrategyMap survives the persistence + read path:
  StrategyMap → model_dump(by_alias=True) → json.dumps → json.loads → StrategyMap

This is the path used by:
  - PersistResults (writes the by_alias dump to DynamoDB)
  - analysis_payload.build_analysis_payload (reads the JSON-decoded
    payload back and forwards it to the API as `strategyMap`)

The aliases are critical here. Several fields use Pydantic aliases
to translate between the snake_case Python identifiers and the
camelCase JSON wire shape:

  - StrategyMap.value_proposition          ↔ "valueProposition"
  - StrategyMap.strategic_priorities       ↔ "strategicPriorities"
  - StrategyMap.internal_processes         ↔ "internalProcesses"
  - StrategyMap.organizational_capacity    ↔ "organizationalCapacity"
  - StrategyMap.core_values                ↔ "coreValues"
  - Arrow.from_id                          ↔ "from"
  - Arrow.to_id                            ↔ "to"

The ``whatsMissing`` field (and its ``Gap`` model) was removed from the
StrategyMap end-to-end under the ``redesign-strategy-map`` Phase 2
change. Legacy persisted records that still carry ``whatsMissing`` data
load without error (the model uses ``extra="allow"``) — see
``TestLegacyTolerance``.

A regression in any alias breaks the wire shape silently — JSON
serialises with one name and a downstream consumer expects another.
"""

from __future__ import annotations

import json

from src.models.model_strategy_map import StrategyMap


def _make_full_strategy_map_dict() -> dict:
    """The camelCase wire shape that the AI generation chain produces."""
    return {
        "vision": {
            "statement": "To be the most appetizing convenience retailer",
            "synthesised": False,
            "rationale": "Verbatim from public materials.",
        },
        "mission": {
            "statement": "Provide convenient food and fuel to commuters.",
            "synthesised": True,
            "rationale": "Synthesised from store-locator content.",
        },
        "valueProposition": {
            "primary": "customer_intimacy",
            "secondary": None,
            "rationale": "Public materials emphasise associate friendliness.",
            "exemplar_company": "Wawa",
        },
        "strategicPriorities": [
            {
                "name": "Grow Through Foodservice",
                "result": "Best-in-class food platform driving same-store growth.",
            },
            {
                "name": "Deliver Convenience and Value",
                "result": "Industry-leading customer perception of speed and value.",
            },
        ],
        "financial": {
            "objectives": [
                {
                    "id": "F1",
                    "title": "Grow profitable revenue across markets",
                    "definition": (
                        "We will grow same-segment revenue by deepening engagement with "
                        "current customers and entering adjacent markets, with year-over-"
                        "year revenue growth as the primary measure of expansion success."
                    ),
                    "category": "revenue_growth",
                    "confidence": "HIGH",
                    "rationale_source": "EBITDA tree revenue branch.",
                },
                {
                    "id": "F2",
                    "title": "Drive operational efficiency",
                    "definition": (
                        "We will improve cost-to-serve metrics by automating routine "
                        "operations, reducing waste in supply chain, and optimising "
                        "labour scheduling against demand patterns."
                    ),
                    "category": "productivity",
                    "confidence": "MEDIUM",
                },
                {
                    "id": "F3",
                    "title": "Maximise return on invested capital",
                    "definition": (
                        "We will allocate capital toward the highest-return store "
                        "formats and geographies, retiring or repositioning stores "
                        "below threshold IRR within a defined refresh cycle."
                    ),
                    "category": "productivity",
                    "confidence": "MEDIUM",
                },
            ]
        },
        "customer": {
            "objectives": [
                {
                    "id": "C1",
                    "title": "Offer me fresh products in a friendly environment",
                    "definition": (
                        "I rely on this brand for fast, friendly service and quality "
                        "products. The associates treat me as a regular."
                    ),
                    "panel": "consumer",
                    "confidence": "HIGH",
                },
                {
                    "id": "C2",
                    "title": "Recognise my loyalty",
                    "definition": (
                        "I expect the loyalty programme to acknowledge my repeated "
                        "visits with meaningful rewards I actually use."
                    ),
                    "panel": "consumer",
                    "confidence": "MEDIUM",
                },
                {
                    "id": "C3",
                    "title": "Make my visit fast and convenient",
                    "definition": (
                        "I want to get in, get what I need, and get out efficiently "
                        "without friction at checkout."
                    ),
                    "panel": "consumer",
                    "confidence": "HIGH",
                },
            ]
        },
        "internalProcesses": {
            "themes": [
                {
                    "name": "Grow Through Foodservice",
                    "supports_financial_objectives": ["F1"],
                    "objectives": [
                        {
                            "id": "I1.1",
                            "title": "Develop signature food and beverage offers",
                            "definition": (
                                "We will create and improve fresh food and beverage "
                                "offers that differentiate the brand and grow basket "
                                "size with regular product platform reviews."
                            ),
                            "category": "innovation",
                            "confidence": "HIGH",
                        }
                    ],
                },
                {
                    "name": "Deliver Convenience and Value",
                    "supports_financial_objectives": ["F1", "F2"],
                    "objectives": [
                        {
                            "id": "I2.1",
                            "title": "Improve end-to-end process throughput",
                            "definition": (
                                "We will continuously improve the throughput, quality, "
                                "and cost of our end-to-end processes through a "
                                "disciplined data-driven approach."
                            ),
                            "category": "operational_excellence",
                            "confidence": "HIGH",
                        }
                    ],
                },
            ]
        },
        "organizationalCapacity": {
            "people": {
                "id": "O.P",
                "title": "Develop our associates as brand ambassadors",
                "definition": (
                    "We will invest in associate development through structured training, "
                    "succession planning, and a culture of ownership."
                ),
                "confidence": "MEDIUM",
            },
            "technology": {
                "id": "O.T",
                "title": "Deliver reliable systems and data-driven insight",
                "definition": (
                    "We will provide consistently reliable technical products and support "
                    "services, with valuable insights for forward-looking decisions."
                ),
                "confidence": "MEDIUM",
            },
            "culture": {
                "id": "O.C",
                "title": "Live our values in every interaction",
                "definition": (
                    "Our values are the foundation of how we work. We will live them "
                    "consistently across the organisation."
                ),
                "confidence": "LOW",
            },
        },
        "arrows": [
            {
                "from": "O.P",
                "to": "I1.1",
                "hypothesis": (
                    "Investing in associate development enables higher-quality "
                    "execution of new food platforms."
                ),
            },
            {
                "from": "I1.1",
                "to": "C1",
                "hypothesis": (
                    "Signature food platforms drive the customer perception of "
                    "fresh, friendly experience."
                ),
            },
            {
                "from": "C1",
                "to": "F1",
                "hypothesis": (
                    "A delighted, returning customer drives same-store revenue "
                    "growth through frequency and basket size."
                ),
            },
            {
                "from": "I2.1",
                "to": "F2",
                "hypothesis": (
                    "Process improvements lower cost-to-serve, contributing "
                    "directly to operational efficiency."
                ),
            },
            {
                "from": "O.T",
                "to": "I2.1",
                "hypothesis": (
                    "Reliable systems and data-driven insight enable the "
                    "disciplined process improvement programme."
                ),
            },
        ],
        "coreValues": {
            "values": ["Care for customers", "Respect for associates", "Continuous improvement"],
            "synthesised": True,
            "rationale": "Synthesised from public materials.",
        },
    }


class TestStrategyMapRoundtrip:
    def test_roundtrip_preserves_full_payload(self):
        """The AI's camelCase JSON survives parse → dump → parse without loss."""
        payload = _make_full_strategy_map_dict()
        # Parse the camelCase wire shape (matches what the AI produces).
        sm = StrategyMap.model_validate(payload)
        # Dump back to camelCase JSON (matches what gets persisted).
        dumped = sm.model_dump(by_alias=True)
        # Re-parse and confirm the structure is stable.
        sm_again = StrategyMap.model_validate(dumped)
        assert sm_again.model_dump(by_alias=True) == dumped

    def test_top_level_aliases_use_camel_case(self):
        sm = StrategyMap.model_validate(_make_full_strategy_map_dict())
        dumped = sm.model_dump(by_alias=True)
        # These must be camelCase in the persisted shape.
        for required in (
            "valueProposition",
            "strategicPriorities",
            "internalProcesses",
            "organizationalCapacity",
            "coreValues",
        ):
            assert required in dumped
        # Snake_case forms must NOT appear (would break the frontend type).
        for forbidden in (
            "value_proposition",
            "strategic_priorities",
            "internal_processes",
            "organizational_capacity",
            "core_values",
        ):
            assert forbidden not in dumped
        # whatsMissing is removed end-to-end and must not appear in fresh dumps.
        assert "whatsMissing" not in dumped
        assert "whats_missing" not in dumped

    def test_arrow_uses_from_to_keys(self):
        """Arrow's `from_id`/`to_id` aliases must serialise as `from`/`to`."""
        sm = StrategyMap.model_validate(_make_full_strategy_map_dict())
        dumped = sm.model_dump(by_alias=True)
        for arrow in dumped["arrows"]:
            assert "from" in arrow
            assert "to" in arrow
            assert "from_id" not in arrow
            assert "to_id" not in arrow

    def test_json_dumps_loads_roundtrip(self):
        """The full DynamoDB persistence path: dump → json.dumps → json.loads → re-validate."""
        payload = _make_full_strategy_map_dict()
        sm = StrategyMap.model_validate(payload)
        dumped = sm.model_dump(by_alias=True)
        wire = json.dumps(dumped)
        decoded = json.loads(wire)
        re_validated = StrategyMap.model_validate(decoded)
        assert re_validated.model_dump(by_alias=True) == dumped


class TestLegacyTolerance:
    """Persisted records from before ``redesign-strategy-map`` Phase 2
    may still carry a ``whatsMissing`` array on the strategy-map JSON.
    The model uses ``extra="allow"``, so those records continue to load
    without error.

    Note: Pydantic's ``extra="allow"`` causes ``model_dump()`` to
    PRESERVE the extra field on re-dump rather than dropping it. No
    production code path round-trips legacy records through Pydantic
    after the load (the load path goes directly to the API response),
    so the field is never inadvertently re-persisted.
    """

    def test_legacy_payload_with_whats_missing_loads_cleanly(self):
        payload = _make_full_strategy_map_dict()
        payload["whatsMissing"] = [
            {
                "id": "G1",
                "title": "Legacy gap title",
                "description": (
                    "This gap was generated by a pre-Phase-2 run and persisted to "
                    "DynamoDB. The new code should accept it without error."
                ),
                "deepDiveFraming": (
                    "A Vector Advisory deep-dive would explore this legacy area."
                ),
                "relatedObjectiveIds": ["O.C"],
            },
        ]
        # Loading the legacy shape must NOT raise.
        sm = StrategyMap.model_validate(payload)
        # The model accepts the field via ``extra="allow"`` — it lives on
        # the instance but isn't part of the typed schema.
        # The canonical re-dump may or may not preserve the extra field
        # depending on Pydantic's behaviour; the contract this test pins
        # is that legacy data doesn't crash the load path.
        assert sm.financial.objectives[0].id == "F1"  # rest of the model intact


class TestStrategyMapNullableOptionalFields:
    """Optional traceability fields must accept ``null`` from the AI.

    OpenAI strict mode requires every property in ``properties`` to be
    in ``required`` and produced by the model. Fields the AI may not
    have ground truth for (e.g. ``rationale_source`` when no specific
    document grounded the inference) are declared as nullable in the
    JSON schema and the model emits ``null``. The Pydantic model must
    accept that or the assemble step will raise ValidationError and
    the entire strategy-map output will fail to persist.
    """

    def test_rationale_source_accepts_null_on_every_objective_type(self) -> None:
        """All four objective types must accept ``rationale_source: null``."""
        payload = _make_full_strategy_map_dict()
        # Inject null on one objective from each perspective.
        payload["financial"]["objectives"][0]["rationale_source"] = None
        payload["customer"]["objectives"][0]["rationale_source"] = None
        payload["internalProcesses"]["themes"][0]["objectives"][0]["rationale_source"] = None
        payload["organizationalCapacity"]["people"]["rationale_source"] = None

        sm = StrategyMap.model_validate(payload)

        # Round-trip preserves the null (does NOT silently coerce to "").
        dumped = sm.model_dump(by_alias=True)
        assert dumped["financial"]["objectives"][0]["rationale_source"] is None
        assert dumped["customer"]["objectives"][0]["rationale_source"] is None
        assert (
            dumped["internalProcesses"]["themes"][0]["objectives"][0]["rationale_source"] is None
        )
        assert dumped["organizationalCapacity"]["people"]["rationale_source"] is None

    def test_exemplar_company_accepts_null(self) -> None:
        """`valueProposition.exemplar_company` is nullable on the wire."""
        payload = _make_full_strategy_map_dict()
        payload["valueProposition"]["exemplar_company"] = None

        sm = StrategyMap.model_validate(payload)

        assert sm.value_proposition.exemplar_company is None
        dumped = sm.model_dump(by_alias=True)
        assert dumped["valueProposition"]["exemplar_company"] is None
