## Round 2 — Financial Objective Detail

You are elaborating ONE financial-perspective objective. The full
title list (Round 1's output) is provided so you can write a
definition that differentiates this objective from its siblings.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition** (from Step 2): {value_proposition}

**EBITDA tree** (already produced by the analysis pipeline):
{ebitda_tree}

**Opportunities** (full list — index references below are 0-based positions in this array):
{opportunities}

**This objective's title**: {objective_title}
**Sibling titles in the same perspective** (do NOT elaborate these):
{sibling_titles}

## Your task

Produce the elaboration JSON for the objective titled above:

```json
{
  "definition": "<50-150 word 'We will…' definition>",
  "category": "<one of: revenue_growth | productivity>",
  "confidence": "<HIGH | MEDIUM | LOW>",
  "rationale_source": "<short note on which input grounds this>",
  "linked_opportunity_indices": [<0-based indices into the opportunities array above>]
}
```

## Rules

- Definition is 50-150 words, "We will…" voice. Reference specific
  EBITDA branches or opportunity categories where possible.
- The definition MUST differentiate from the sibling titles — do not
  describe what a sibling would describe.
- `category`: revenue_growth or productivity. This feeds the visual
  layout.
- `confidence`: HIGH if directly derived from EBITDA-tree numerics;
  MEDIUM if industry-pattern matched; LOW if inferred from sparse
  signal.
- `rationale_source`: short note for downstream traceability
  (e.g. "EBITDA tree: revenue branch grows 12% per opportunity #3"),
  not for end-user display. Use `null` only if no input directly
  supports this objective.
- `linked_opportunity_indices`: 0-based indices into the
  **Opportunities** array shown above. List ONLY opportunities whose
  execution would directly and materially advance THIS objective —
  not opportunities that are merely adjacent or that advance a
  sibling. Most financial objectives have 1-4 linked opportunities;
  use an empty list `[]` when no opportunity in the list applies.
  Indices MUST be non-negative integers and MUST be in range
  (i.e. 0 to N-1 where N is the length of the opportunities array).
- Do NOT include `id` or `title` in the output — both are assigned
  by the assembly layer based on Round 1's title-list position.

## Example

```json
{
  "definition": "We will grow same-segment revenue by deepening engagement with current enterprise customers, expanding feature adoption, and improving net retention. We will know we have been successful when we attract new logos at a steady cadence, additional usage from current customers, and expanded average contract value through cross-sell of adjacent capabilities.",
  "category": "revenue_growth",
  "confidence": "HIGH",
  "rationale_source": "EBITDA tree shows 60% revenue contribution from existing-segment expansion; aligns with opportunities #1 and #4 (cross-sell).",
  "linked_opportunity_indices": [0, 3]
}
```

Output JSON only. No prose around it.
