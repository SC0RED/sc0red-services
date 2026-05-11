## Mission Synthesis Decision (decomposed)

You are deciding whether the mission statement for this company's
strategy map will need to be SYNTHESISED (because the company has no
published mission) or used VERBATIM (because the company has one).

This is a separate call running in parallel with the mission-text
call. You do not see the generated mission text — judge purely from
the inputs.

## Company under analysis

**Company name**: {company_name}
**URL**: {company_url}
**Industry**: {industry}

**Scraped content** (about-us, mission, values, investor copy):
{scraped_content}

**Optional uploaded document text** (if provided by the user):
{document_text}

## Your task

Produce JSON with exactly TWO fields:

```json
{
  "synthesised": <true|false>,
  "rationale": "<one sentence, 10-300 characters>"
}
```

## Rules

- `synthesised: false` → the company has a published mission statement
  in the scraped content or uploaded document, and the mission-text
  call should be using it verbatim.
- `synthesised: true` → no published mission exists, and the mission-
  text call should synthesise one.
- `rationale` is one sentence:
  - When `synthesised: false`: cite the source.
  - When `synthesised: true`: explain WHY no published mission exists
    and what materials grounded the synthesis.

## Examples

```json
{
  "synthesised": false,
  "rationale": "Verbatim from the company's 'Who We Are' page."
}
```

```json
{
  "synthesised": true,
  "rationale": "Synthesised from public store-locator and brand materials; no explicit mission statement is published."
}
```

Output JSON only. No prose around it.
