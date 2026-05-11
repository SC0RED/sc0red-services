## Mission Statement Generation (decomposed)

You are generating ONLY the mission statement for a 7-step strategy map.
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
  "statement": "<mission sentence, 10-300 characters>"
}
```

## Rules

- If the company has a published mission statement, USE IT VERBATIM.
- If none exists, SYNTHESISE one from public materials.
- Mission is current-tense ("we provide…", "we deliver…"). Not
  aspirational.
- The statement appears in the final map plainly (no quote marks); do
  NOT include surrounding quotation marks in the JSON value itself.
- Avoid vanity language. Be specific about what the company does and
  for whom.
- 10-300 characters. One or two sentences.

## Examples

```json
{ "statement": "Provide an appetizing, convenient food, beverage, and fuel experience in the U.S. mid-Atlantic." }
```

```json
{ "statement": "Engineer and deliver braking systems to OEM and aftermarket customers across heavy-duty truck and commercial-vehicle segments." }
```

Output JSON only. No prose around it.
