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

Answer ONE question: is the arrow `{from_id} → {to_id}` one of the
**5-8 strongest, most strategically central** cause-and-effect links
in this company's entire strategy map?

A Kaplan-Norton strategy map deliberately shows only the FEW arrows
that tell the strategic story — not every plausible connection. Across
ALL candidate pairs being evaluated in parallel right now, expect
approximately 5-8 to be true. Most candidates should return
`enables: false`. Default to `false`; only flip to `true` when the
mechanism is so specific, central, and important that omitting this
arrow would damage the strategic story.

Produce JSON:

```json
{
  "enables": <true|false>,
  "hypothesis": "<one sentence naming the specific mechanism, or null when enables=false>"
}
```

## Rules

- **Default to `enables: false`.** The bar for `true` is high: the
  arrow must represent a load-bearing causal link in this company's
  strategy. Plausible-but-secondary links should be `false`.
- `enables: true` requires a SPECIFIC, COMPANY-CONTEXT-GROUNDED
  mechanism. Generic "X enables Y" is NOT a mechanism. The hypothesis
  must reference concrete signals from THIS company's inputs (the
  vision, value proposition, perspective objective definitions).
- **When `enables: true`, `hypothesis` MUST be a non-null string of
  20-500 characters naming the specific mechanism.** This is a strict
  contract — `{enables: true, hypothesis: null}` is rejected by the
  assembly layer and fails the entire strategy-map generation. The
  schema permits the null type so that `enables: false` can return
  `hypothesis: null`, but you MUST NOT combine `enables: true` with
  a null hypothesis.
- When `enables: false`, set `hypothesis` to `null` (this is the only
  case where null is permitted).
- Examples of GOOD reasoning for `enables: true`:
  - "Investing in associate training enables associates to deliver
    the friendly, knowledgeable in-store experience the brand
    promises."
- Examples of reasoning that should produce `enables: false`:
  - "O.P enables I1.4." (no mechanism named)
  - "Better people produce better outcomes." (generic, not company-
    specific)
  - "This is plausible but isn't one of the top 5-8 most important
    arrows." (acknowledge plausibility ≠ centrality)
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
