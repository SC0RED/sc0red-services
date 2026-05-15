# Per-Call Schemas

The 19 JSON Schemas in this directory are passed to OpenAI's structured-output mode (`response_format`) as the contract for each decomposed AI call in the strategy-map pipeline. They're intentionally narrower than the assembled `strategy_map_output.json` schema — each one describes exactly the fields that one decomposed call is expected to return.

Splitting one big schema into many small ones is what makes the decomposed pipeline (`generate_strategy_map.py` + `_strategy_map_perspectives.py` + `_strategy_map_synthesis.py` + `_strategy_map_arrows.py`) shippable:

- **Throughput.** Each call returns ≤ 1.5 KB of JSON instead of one ~12 KB blob — OpenAI's parallel quota lets 20+ small calls run concurrently.
- **Fast-fail.** A malformed response trips its per-call schema *at the call boundary* (in `ai_call.py`'s `run_structured_ai_call`), not 20 calls later at assembly time. The error message points at the exact call.
- **Prompt clarity.** Each prompt template can lean on the narrow schema for output structure rather than re-stating field constraints in prose.

## Naming convention

| Pattern | Purpose |
|---|---|
| `<perspective>_titles.json` | Round 1 of per-perspective decomposition — returns objective titles only. |
| `<perspective>_objective_detail.json` | Round 2 of per-perspective decomposition — definition / category / confidence / rationale_source for one objective. |
| `internal_themes.json` | Internal-processes Round 1 — list of themes with `supports_financial_objectives` links. |
| `internal_titles_per_theme.json` | Internal-processes Round 2 — objective titles within one theme. |
| `vision_text.json` / `mission_text.json` | Step 1 — raw text generation. |
| `synth_yesno.json` | Step 1 — boolean synthesis check ("does the company already publish this?"). |
| `vp_<facet>.json` | Step 2 — value-proposition primary / secondary / exemplar / rationale. |
| `arrow_yesno.json` | Step 7 — single (from_id, to_id) edge yes/no + hypothesis. |
| `arrows_priorities.json` | Step 7 — strategic priorities holistic synthesis. |
| `core_values.json` | Step 1 — culture summary. |

## Hard rules

Every per-call schema MUST:

1. Set **`$schema: http://json-schema.org/draft-07/schema#`** and **`type: object`** at the top level.
2. Set **`additionalProperties: false`**. This is enforced by `test_strategy_map_schema_strict_mode.py::PerCallSchemas` — adding a new schema without it will fail the suite.
3. List **every property** as `required`. JSON Schema's `required` means "the key must be present"; it is independent of whether the value may be null. Nullable fields like `rationale_source` (typed `["string", "null"]`) are *still* `required` — the AI must always emit the key, but the value may be `null`. OpenAI's structured-output mode is strict about this; omitting a key from `required` allows the model to drop the key entirely, which then trips Pydantic validation downstream. Strict-mode also asserts this.
4. **NOT include the `id` field** for objective-detail schemas. Per Decision §2 of `optimize-strategy-map-latency` (now archived under `redesign-strategy-map`), positional IDs (`F1`/`C2`/`I1.3`/`O.P` etc.) are assigned by `_strategy_map_assembly.py` from title-list order — never requested from the model. This is asserted by `test_strategy_map_decomposed_loaders.py::test_detail_schemas_omit_id_field`.
5. **NOT include the `title` field** for detail schemas — titles come from Round 1 as input to the Round 2 prompt; they're not re-emitted.

## Pydantic alignment

Detail schemas correspond 1:1 to fields of the matching Pydantic models in `backend/src/models/model_strategy_map.py`:

| Per-call schema | Pydantic model | Excluded fields |
|---|---|---|
| `financial_objective_detail.json` | `FinancialObjective` | `id`, `title` |
| `customer_objective_detail.json` | `CustomerObjective` | `id`, `title` |
| `internal_objective_detail.json` | `InternalProcessObjective` | `id`, `title` |
| `capacity_objective_detail.json` | `CapacityObjective` | `id`, `title` |

The alignment is asserted by `test_strategy_map_per_call_schemas.py` — adding a field to the Pydantic model without updating the matching schema (or vice versa) trips a test.

## Validation pipeline

```
OpenAI response  ──►  jsonschema.validate (per-call schema)  ──►  assembly  ──►  StrategyMap (Pydantic)
                       │
                       └── done inside run_structured_ai_call;
                           ValidationError raised with the call label
                           so failures point at the exact OpenAI call.
```

Pydantic still validates the assembled output — the per-call validator is a **fast-fail boundary check** that catches malformed OpenAI responses immediately rather than letting them propagate to assembly.

## Adding a new per-call schema

1. Create the schema following the hard rules above.
2. If it corresponds to a Pydantic model field subset, add the mapping in `test_strategy_map_per_call_schemas.py`.
3. Reference the schema from the matching prompt template loader in `_strategy_map_corpus.py`.
4. Run `uv run pytest tests/unit/pipeline/test_strategy_map_schema_strict_mode.py tests/unit/pipeline/test_strategy_map_per_call_schemas.py -q` to confirm strict-mode + Pydantic-alignment pass.
