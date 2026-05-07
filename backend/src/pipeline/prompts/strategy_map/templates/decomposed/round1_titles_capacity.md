## Round 1 — Organizational Capacity Titles

You are generating Step 6 of a strategy map. Organizational
Capacity has THREE FIXED BUCKETS — People, Technology, Culture —
that show up the same way in every strategy map. This call
produces ONLY the **per-bucket title**. Definitions and elaboration
come in a Round 2 call per bucket.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition**: {value_proposition}
**Internal-processes themes**: {internal_processes}

**Profile**:
{profile_summary}

**Tech signals** (from profile / scrape):
{tech_signals}

**Operational risk signals**:
{operational_risk_signals}

## Your task

Produce **one short imperative title for each of the three fixed
buckets**:

- `people` — workforce, training, talent.
- `technology` — systems, data, tooling, AI/automation.
- `culture` — values, behaviours, leadership, ways of working.

Output JSON:

```json
{
  "people": "<short imperative title for the people bucket>",
  "technology": "<short imperative title for the technology bucket>",
  "culture": "<short imperative title for the culture bucket>"
}
```

## Rules

- All three buckets MUST be present (no nulls; the buckets are
  fixed, only the title varies).
- Each title is a short imperative phrase, 5-15 words.
- Titles must clearly belong to their bucket — don't put a
  technology objective under `people`, etc.
- Do NOT include `id`, `definition`, or other fields.

## Example

```json
{
  "people": "Develop our associates as ambassadors",
  "technology": "Deliver reliable systems and insight",
  "culture": "Live our values in every interaction"
}
```

Output JSON only. No prose around it.
