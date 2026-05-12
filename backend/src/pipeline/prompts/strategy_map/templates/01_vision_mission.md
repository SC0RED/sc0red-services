## Step 1 — Vision and Mission Synthesis

You are generating Step 1 of a 7-step strategy map for the company
described below. This step produces the vision and mission statements
that anchor the rest of the map.

## Company under analysis

**Company name**: {company_name}
**URL**: {company_url}
**Industry**: {industry}

**Scraped content** (about-us, mission, values, investor copy):
{scraped_content}

**Optional uploaded document text** (if provided by the user):
{document_text}

## Your task

Produce JSON with two fields:

```json
{
  "vision": {
    "statement": "<quoted vision sentence>",
    "synthesised": <true|false>,
    "rationale": "<one sentence: where you got this, or why you synthesised>"
  },
  "mission": {
    "statement": "<plain-language mission sentence>",
    "synthesised": <true|false>,
    "rationale": "<one sentence>"
  }
}
```

## Rules

- If the company has a published vision statement on its website,
  USE IT VERBATIM and set `synthesised: false`.
- If no published vision exists, GENERATE ONE from public materials.
  Set `synthesised: true`. Make it specific (name a segment,
  outcome, position, or geography per `anti_patterns.md`).
- The vision statement appears in the final map in quote marks; do
  not include the quote marks in the JSON value itself.
- Mission is current-tense ("we provide…", "we deliver…"). Vision is
  aspirational ("to become…", "to be…").
- Avoid vanity language. Vague visions ("delight customers", "create
  value") are not acceptable. If the company's published vision is
  vanity-grade, surface that as a candidate gap by setting
  `synthesised: false` (we used what they have) but flag in the
  rationale.

## Examples (from the exemplars)

```json
{
  "vision": {
    "statement": "To be the world's most appetizing convenience retailer.",
    "synthesised": false,
    "rationale": "Verbatim from the company's 2011 corporate strategy deck."
  },
  "mission": {
    "statement": "Provide an appetizing, convenient food, beverage, and fuel experience in the U.S. mid-Atlantic.",
    "synthesised": true,
    "rationale": "Synthesised from public store-locator and brand materials; no explicit mission statement is published."
  }
}
```

Output JSON only. No prose around it.
