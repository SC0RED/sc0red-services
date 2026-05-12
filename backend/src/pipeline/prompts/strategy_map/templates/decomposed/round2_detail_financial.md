## Round 2 — Financial Objective Detail

You are elaborating ONE financial-perspective objective. The full
title list (Round 1's output) is provided so you can write a
definition that differentiates this objective from its siblings.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition** (from Step 2): {value_proposition}

**EBITDA tree** (already produced by Janus):
{ebitda_tree}

**Top opportunities**:
{top_opportunities}

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
  "rationale_source": "<short note on which input grounds this>"
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
- Do NOT include `id` or `title` in the output — both are assigned
  by the assembly layer based on Round 1's title-list position.

## Example

```json
{
  "definition": "We will grow same-segment revenue by deepening engagement with current enterprise customers, expanding feature adoption, and improving net retention. We will know we have been successful when we attract new logos at a steady cadence, additional usage from current customers, and expanded average contract value through cross-sell of adjacent capabilities.",
  "category": "revenue_growth",
  "confidence": "HIGH",
  "rationale_source": "EBITDA tree shows 60% revenue contribution from existing-segment expansion; aligns with opportunities #1 and #4 (cross-sell)."
}
```

Output JSON only. No prose around it.
