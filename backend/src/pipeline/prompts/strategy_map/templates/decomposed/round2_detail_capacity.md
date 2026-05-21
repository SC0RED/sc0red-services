## Round 2 — Organizational Capacity Objective Detail

You are elaborating ONE organizational-capacity bucket
(people, technology, or culture).

## Inputs

**Company name**: {company_name}
**Customer Value Proposition**: {value_proposition}
**Internal-processes themes**: {internal_processes}

**Profile**:
{profile_summary}

**Tech signals**:
{tech_signals}

**Opportunities** (full list — index references below are 0-based positions in this array):
{opportunities}

**This bucket**: {bucket}
**This objective's title**: {objective_title}
**Sibling capacity titles**:
{sibling_titles}

## Your task

Produce the elaboration JSON for this capacity bucket:

```json
{
  "definition": "<50-150 word 'We will…' definition>",
  "confidence": "<HIGH | MEDIUM | LOW>",
  "rationale_source": "<short traceability note or null>",
  "linked_opportunity_indices": [<0-based indices into the opportunities array above>]
}
```

## Rules

- Definition is 50-150 words, "We will…" voice. Anchor to specifics:
  for `people`, name the capability we're building (training,
  hiring, deployment); for `technology`, name the systems / data
  domain; for `culture`, name the values / behaviours and how
  they're reinforced.
- The definition MUST differentiate from the other two capacity
  bucket titles listed above.
- Capacity objectives have NO `category` field (unlike the other
  perspectives).
- `confidence`: HIGH if grounded in profile or tech-signal data;
  MEDIUM if industry-pattern matched; LOW if inferred.
- `rationale_source`: short note for traceability or `null`.
- `linked_opportunity_indices`: 0-based indices into the
  **Opportunities** array shown above. List ONLY opportunities whose
  execution would directly and materially advance THIS capacity
  bucket — for `people`, opportunities that build talent / hiring /
  training; for `technology`, opportunities that build platform or
  data capability; for `culture`, opportunities that shape values or
  behaviours. Most capacity buckets have 0-3 linked opportunities;
  use an empty list `[]` when no opportunity in the list applies.
  Indices MUST be non-negative integers and MUST be in range
  (0 to N-1 where N is the length of the opportunities array).
- Do NOT include `id`, `title`, or `category`.

## Example (for the `people` bucket)

```json
{
  "definition": "We will invest in associate development through structured training programmes, customer-service rituals, and visible career pathways from store associate to manager. We will know we have been successful when associate engagement scores rise, voluntary turnover drops to industry benchmark, and customer-satisfaction scores correlate to store-level associate tenure.",
  "confidence": "MEDIUM",
  "rationale_source": "Profile mentions associate ownership program; opportunities cluster around 'develop frontline talent'.",
  "linked_opportunity_indices": [2]
}
```

Output JSON only. No prose around it.
