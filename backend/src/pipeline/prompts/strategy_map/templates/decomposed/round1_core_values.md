## Round 1 — Core Values

You are extracting (or synthesising) the company's **core values**.
Core values are 3-6 short noun phrases that capture how the company
intends to operate. They appear alongside the strategy map but
aren't part of any one perspective.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition**: {value_proposition}

**Profile**:
{profile_summary}

**Public materials / mission text**:
{vision_statement}

{mission_statement}

## Your task

Produce 3-6 core values as short noun phrases. If the company
publishes its core values in the inputs above, prefer those (set
`synthesised: false`). Otherwise synthesise plausible values from
the mission, vision, and profile — set `synthesised: true` and
explain in `rationale`.

Output JSON:

```json
{
  "values": ["<value 1>", "<value 2>", "<value 3>"],
  "synthesised": false,
  "rationale": "<10-50 word note on whether these are published or synthesised>"
}
```

## Rules

- 3 to 6 values.
- Each value is a short noun phrase, 1-3 words ideally (max 4 if
  needed for clarity). Examples: "Care", "Respect", "Continuous
  improvement", "Customer obsession", "Operational discipline".
- `synthesised: false` if directly quoted from the company's
  published materials; `true` otherwise.
- `rationale` notes whether published or synthesised, and what
  source if applicable. 10-50 words.

## Example (synthesised)

```json
{
  "values": ["Care", "Respect", "Continuous improvement"],
  "synthesised": true,
  "rationale": "Synthesised from public materials emphasising associate ownership and customer-first messaging; no formal published values list found."
}
```

Output JSON only. No prose around it.
