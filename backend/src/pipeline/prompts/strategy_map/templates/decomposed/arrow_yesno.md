## Arrow Yes/No (decomposed)

You are evaluating ONE candidate cause-and-effect arrow between two
strategy-map objectives. Many calls like this run in parallel, one per
candidate pair.

## Inputs

**Company name**: {company_name}
**Vision**: {vision_statement}
**Customer Value Proposition**: {value_proposition}

**Candidate arrow**:
- **FROM** objective `{from_id}`: "{from_title}"
- **TO** objective `{to_id}`: "{to_title}"

**Full strategy map context** (so you can reason about the mechanism):
- Financial objectives: {financial_objectives}
- Customer objectives: {customer_objectives}
- Internal Processes: {internal_processes}
- Organizational Capacity: {organizational_capacity}

## Your task

Answer ONE question: does objective `{from_id}` plausibly ENABLE
objective `{to_id}` via a specific, testable cause-and-effect
mechanism?

Produce JSON:

```json
{
  "enables": <true|false>,
  "hypothesis": "<one sentence naming the specific mechanism, or null when enables=false>"
}
```

## Rules

- `enables: true` only when there is a SPECIFIC mechanism connecting
  the two objectives. Generic "X enables Y" is NOT a mechanism.
- **When `enables: true`, `hypothesis` MUST be a non-null string of
  20-500 characters naming the specific mechanism.** This is a strict
  contract — `{enables: true, hypothesis: null}` is rejected by the
  assembly layer and fails the entire strategy-map generation. The
  schema permits the null type so that `enables: false` can return
  `hypothesis: null`, but you MUST NOT combine `enables: true` with
  a null hypothesis.
- When `enables: false`, set `hypothesis` to `null` (this is the only
  case where null is permitted).
- The `hypothesis` field MUST name the mechanism. Examples:
  - GOOD: "Investing in associate training enables associates to
    deliver the friendly, knowledgeable in-store experience the brand
    promises."
  - BAD: "O.P enables I1.4." (no mechanism)
  - BAD: "Better people produce better outcomes." (generic)
- Direction MUST be forward in the causal hierarchy: Capacity →
  Internal Process → Customer → Financial. If the candidate runs
  backward, set `enables: false`.

## Examples

```json
{
  "enables": true,
  "hypothesis": "Investing in associate training (O.P) enables associates to deliver the friendly, knowledgeable in-store experience the brand promises (I1.4)."
}
```

```json
{
  "enables": false,
  "hypothesis": null
}
```

Output JSON only. No prose around it.
