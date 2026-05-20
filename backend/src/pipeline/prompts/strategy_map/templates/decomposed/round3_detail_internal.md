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

**Opportunities** (full list — index references below are 0-based positions in this array):
{opportunities}

## Your task

Produce the elaboration JSON for this objective:

```json
{
  "definition": "<50-150 word 'We will…' definition>",
  "category": "<one of: innovation | customer_management | operational_excellence | citizenship>",
  "confidence": "<HIGH | MEDIUM | LOW>",
  "rationale_source": "<short traceability note or null>",
  "linked_opportunity_indices": [<0-based indices into the opportunities array above>]
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
- `linked_opportunity_indices`: 0-based indices into the
  **Opportunities** array shown above. List ONLY opportunities whose
  execution would directly and materially advance THIS internal-
  process objective — not opportunities that are merely adjacent or
  that advance a sibling within the same theme. Internal-process
  objectives are usually the densest linkage target (this is where
  the day-to-day work happens); 2-5 linked opportunities is typical.
  Use an empty list `[]` when no opportunity in the list applies.
  Indices MUST be non-negative integers and MUST be in range
  (0 to N-1 where N is the length of the opportunities array).
- Do NOT include `id` or `title` in the output.

## Example

```json
{
  "definition": "We will continuously develop signature fresh-food and beverage offers that differentiate from category competitors. We will refresh menu items on a quarterly cadence, expand local-sourcing where viable, and use loyalty data to test new SKUs at limited stores before national rollout. We will know we have been successful when same-store sales of fresh categories outpace the category index over consecutive quarters.",
  "category": "innovation",
  "confidence": "HIGH",
  "rationale_source": "Value chain step 'Product Development' has clear opportunity ranking #1; opportunities include 'Develop signature fresh-food offers' as Quick Win.",
  "linked_opportunity_indices": [0, 3]
}
```

Output JSON only. No prose around it.
