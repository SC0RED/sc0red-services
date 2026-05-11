## Vision Statement Generation (decomposed)

You are generating ONLY the vision statement for a 7-step strategy map.
Synthesised flag and rationale come from a separate call running in
parallel — do not include them here.

## Company under analysis

**Company name**: {company_name}
**URL**: {company_url}
**Industry**: {industry}

**Scraped content** (about-us, mission, values, investor copy):
{scraped_content}

**Optional uploaded document text** (if provided by the user):
{document_text}

## Your task

Produce JSON with exactly ONE field:

```json
{
  "statement": "<vision sentence, 10-200 characters>"
}
```

## Rules

- If the company has a published vision statement on its website,
  USE IT VERBATIM.
- If no published vision exists, GENERATE one from public materials.
  Make it specific (name a segment, outcome, position, or geography
  per `anti_patterns.md`).
- Vision is aspirational ("to become…", "to be…"). Not current-tense.
- The statement appears in the final map in quote marks; do NOT
  include surrounding quotation marks in the JSON value itself.
- Avoid vanity language. Vague visions ("delight customers", "create
  value") are not acceptable.
- 10-200 characters. Keep it sentence-length.

## Examples

```json
{ "statement": "To be the world's most appetizing convenience retailer." }
```

```json
{ "statement": "To dominate the global automotive aftermarket through engineered braking systems." }
```

Output JSON only. No prose around it.
