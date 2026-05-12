## Vision Synthesis Decision (decomposed)

You are deciding whether the vision statement for this company's
strategy map will need to be SYNTHESISED (because the company has no
published vision) or used VERBATIM (because the company has one).

This is a separate call running in parallel with the vision-text call.
You do not see the generated vision text — judge purely from the
inputs.

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

- `synthesised: false` → the company has a published vision statement
  in the scraped content or uploaded document, and the vision-text
  call should be using it verbatim.
- `synthesised: true` → no published vision exists, and the vision-text
  call should generate one.
- `rationale` is one sentence:
  - When `synthesised: false`: cite the source ("Verbatim from the
    company's 2024 annual report" / "Quoted directly from the 'About
    Us' page").
  - When `synthesised: true`: explain WHY no published vision exists
    and what materials grounded the synthesis ("No published vision
    statement; synthesised from product-line copy and the CEO's
    LinkedIn 'About' section").
- If a published vision is vanity-grade (e.g. "delight customers"),
  set `synthesised: false` (we used what they have) but flag in the
  rationale that the published vision is weak.

## Examples

```json
{
  "synthesised": false,
  "rationale": "Verbatim from the company's 2011 corporate strategy deck."
}
```

```json
{
  "synthesised": true,
  "rationale": "No published vision statement; synthesised from product-portfolio descriptions and the 'Investors' page strategic overview."
}
```

Output JSON only. No prose around it.
