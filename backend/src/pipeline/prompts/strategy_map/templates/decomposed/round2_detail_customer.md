## Round 2 — Customer Objective Detail

You are elaborating ONE customer-perspective objective.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition**: {value_proposition}

**Profile**:
{profile_summary}

**Top opportunities**:
{top_opportunities}

**This objective's title**: {objective_title}
**Sibling titles in the same perspective**:
{sibling_titles}

## Your task

Produce the elaboration JSON for this objective:

```json
{
  "definition": "<50-150 word definition>",
  "panel": "<consumer | channel | partner>",
  "confidence": "<HIGH | MEDIUM | LOW>",
  "rationale_source": "<short traceability note or null>"
}
```

## Rules

- Definition is 50-150 words. Use the panel's voice: "I rely on…",
  "We rely on…", or "We depend on…" depending on whether the panel
  is consumer / channel / partner respectively.
- The definition MUST differentiate from the sibling titles.
- `panel` distinguishes the audience tier:
  - `consumer` — end-buyer/end-consumer.
  - `channel` — distributor/reseller/retailer.
  - `partner` — strategic partner/supplier/alliance.
- `confidence`: HIGH if directly observable from profile data;
  MEDIUM if industry-pattern matched; LOW if inferred.
- `rationale_source`: short note for traceability or `null`.
- Do NOT include `id` or `title` in the output.

## Example

```json
{
  "definition": "I rely on this brand for fast, friendly service and consistent quality. I expect the in-store environment to be welcoming and the assortment to feature fresh, locally relevant products. We will know we have been successful when consumers report higher satisfaction scores and visit frequency rises across stores.",
  "panel": "consumer",
  "confidence": "HIGH",
  "rationale_source": "Profile: brand mission emphasises fresh and friendly; opportunities #2, #5 reinforce store-experience uplift."
}
```

Output JSON only. No prose around it.
