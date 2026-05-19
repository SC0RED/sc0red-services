## Round 1 — Financial Perspective Titles

You are generating Step 3 of a strategy map. This call produces ONLY
the **list of 3 financial-objective titles**. Definitions and
categorisation come in a separate Round 2 call per title.

## Inputs

**Company name**: {company_name}
**Vision**: {vision_statement}
**Customer Value Proposition** (from Step 2): {value_proposition}

**EBITDA tree** (already produced by the analysis pipeline):
{ebitda_tree}

**Top-level revenue / EBITDA estimates**:
- Revenue estimate: {revenue_estimate}
- EBITDA estimate: {ebitda_estimate}

**Top opportunities** (already classified by the analysis pipeline):
{top_opportunities}

## Your task

Produce **exactly 3 short, imperative titles** for the financial
perspective. Per the K&N framework, the financial perspective
balances Revenue Growth with Productivity. Aim for a 2-1 split (2
revenue-side + 1 productivity, or vice versa) based on which side
has more momentum in the EBITDA tree.

Output JSON only:

```json
{
  "titles": [
    "<title 1, 5-12 words, imperative voice>",
    "<title 2, 5-12 words, imperative voice>",
    "<title 3, 5-12 words, imperative voice>"
  ]
}
```

## Rules

- Exactly 3 titles, in priority order. Position 1 → most strategically
  important objective for this company; position 3 → least.
- Each title is a short imperative phrase, 5-12 words. Avoid
  corporate buzzwords. No quotation marks inside titles.
- Titles MUST differentiate from each other (no near-duplicates).
- Do NOT include `id`, `definition`, or any other fields. Those are
  Round 2's job.

## Example

```json
{
  "titles": [
    "Grow revenue and customer count in existing markets",
    "Drive operational efficiency through automation",
    "Maximise return on invested capital"
  ]
}
```

Output JSON only. No prose around it.
