## Step 3 — Financial Perspective Objectives

You are generating Step 3 of a 7-step strategy map. This step
produces 3 Financial perspective objectives.

## Inputs

**Company name**: {company_name}
**Vision**: {vision_statement}
**Customer Value Proposition** (from Step 2): {value_proposition}

**EBITDA tree** (already produced by Janus):
{ebitda_tree}

**Top-level revenue / EBITDA estimates**:
- Revenue estimate: {revenue_estimate}
- EBITDA estimate: {ebitda_estimate}

**Top opportunities** (already classified by Janus):
{top_opportunities}

## Your task

Produce 3 Financial perspective objectives. Per the K&N framework,
Financial perspective typically balances Revenue Growth with
Productivity (cost / asset utilisation). Aim for a 2-1 split
(2 revenue-side + 1 productivity, or 1 revenue + 2 productivity)
based on which side has more momentum in the EBITDA tree and
opportunities.

Produce JSON:

```json
{
  "financial": {
    "objectives": [
      {
        "id": "F1",
        "title": "<imperative title, e.g. 'Grow revenue and customer count in target markets'>",
        "definition": "<50-150 word 'We will…' definition>",
        "category": "<one of: revenue_growth | productivity>",
        "confidence": "<HIGH | MEDIUM | LOW>",
        "rationale_source": "<short note on which input grounds this>"
      },
      ...
    ]
  }
}
```

## Rules

- Exactly 3 objectives.
- IDs are F1, F2, F3 in order.
- Titles are short imperatives (5-12 words). Avoid corporate buzzwords.
- Definitions are 50-150 words, "We will…" voice. Reference specific
  EBITDA branches or opportunity categories where possible.
- `category` distinguishes revenue_growth from productivity; this
  feeds the visual layout.
- `confidence` per the rules in the system prompt: HIGH if directly
  derived from EBITDA tree numerics; MEDIUM if industry-pattern
  matched; LOW if inferred.
- `rationale_source` is a short note for downstream traceability
  (e.g. "EBITDA tree: revenue branch grows 12% per opportunity #3"),
  not for end-user display.

## Example

```json
{
  "financial": {
    "objectives": [
      {
        "id": "F1",
        "title": "Grow revenue and customer count in existing markets",
        "definition": "We will grow same-segment revenue by deepening engagement with current enterprise customers, expanding feature adoption, and improving net retention. We will know we have been successful when we attract new logos at a steady cadence, additional usage from current customers, and expanded average contract value through cross-sell of adjacent capabilities.",
        "category": "revenue_growth",
        "confidence": "HIGH",
        "rationale_source": "EBITDA tree shows 60% revenue contribution from existing-segment expansion; aligns with opportunities #1 and #4 (cross-sell)."
      }
    ]
  }
}
```

Output JSON only. No prose around it.
