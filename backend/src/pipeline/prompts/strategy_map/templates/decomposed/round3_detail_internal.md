## Round 3 — Internal-Processes Objective Detail

You are elaborating ONE internal-processes objective.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition**: {value_proposition}

**This objective's theme**: {theme_name}
**This theme supports financial objectives**: {supports_financial_objectives}
**This objective's title**: {objective_title}
**Sibling titles in the same theme**:
{sibling_titles}

**Value chain analysis**:
{value_chain}

**Opportunities**:
{opportunities}

## Your task

Produce the elaboration JSON for this objective:

```json
{
  "definition": "<50-150 word 'We will…' definition>",
  "category": "<one of: innovation | customer_management | operational_excellence | citizenship>",
  "confidence": "<HIGH | MEDIUM | LOW>",
  "rationale_source": "<short traceability note or null>"
}
```

## Rules

- Definition is 50-150 words, "We will…" voice. Reference specific
  value-chain steps or opportunity categories where possible.
- The definition MUST differentiate from the sibling titles in the
  same theme.
- `category`:
  - `innovation` — new products / experiences / signature offers.
  - `customer_management` — relationship, retention, loyalty.
  - `operational_excellence` — throughput, cost, quality, supply chain.
  - `citizenship` — sustainability, regulatory, community.
- `confidence`: HIGH if directly observable in value chain or
  opportunities; MEDIUM if industry-pattern matched; LOW if inferred.
- `rationale_source`: short note for traceability or `null`.
- Do NOT include `id` or `title` in the output.

## Example

```json
{
  "definition": "We will continuously develop signature fresh-food and beverage offers that differentiate from category competitors. We will refresh menu items on a quarterly cadence, expand local-sourcing where viable, and use loyalty data to test new SKUs at limited stores before national rollout. We will know we have been successful when same-store sales of fresh categories outpace the category index over consecutive quarters.",
  "category": "innovation",
  "confidence": "HIGH",
  "rationale_source": "Value chain step 'Product Development' has clear opportunity ranking #1; opportunities include 'Develop signature fresh-food offers' as Quick Win."
}
```

Output JSON only. No prose around it.
