## Step 7 — Arrows and "What's Missing?" Gaps

You are generating Step 7 (the final step) of a 7-step strategy map.
This step produces:

1. **Cause-and-effect arrows** between objectives across perspectives
   (the "linked hypotheses" that make a strategy map a strategy).
2. **Strategic priorities** (3 named priorities matching the Internal
   Processes themes from Step 5, with "Strategic Results" each).
3. **"What's Missing?" gaps** (2-4 strategic gaps that drive the
   deep-dive CTA).

## Inputs

**Vision**: {vision}
**Customer Value Proposition**: {value_proposition}
**Financial objectives** (Step 3): {financial_objectives}
**Customer objectives** (Step 4): {customer_objectives}
**Internal Processes themes** (Step 5): {internal_processes}
**Organizational Capacity** (Step 6): {organizational_capacity}
**Confidence markers** (across all objectives): {confidence_summary}

## Your task

Produce JSON with three top-level fields:

```json
{
  "strategicPriorities": [
    {
      "name": "<theme name from Step 5>",
      "result": "<one-sentence success statement>"
    }
  ],
  "arrows": [
    {
      "from": "<objective ID, e.g. O.P>",
      "to": "<objective ID, e.g. I1.1>",
      "hypothesis": "<one-sentence cause-effect claim>"
    }
  ],
  "whatsMissing": [
    {
      "id": "G1",
      "title": "<short gap label>",
      "description": "<1-2 sentences explaining why public-data analysis cannot resolve this gap>",
      "deepDiveFraming": "<1 sentence framing what a Vector Advisory deep-dive engagement would address>",
      "relatedObjectiveIds": ["<optional list of objective IDs the gap touches>"]
    }
  ]
}
```

## Strategic Priorities

- Reuse the theme names from Step 5's `internalProcesses.themes`. The
  count matches (2-3).
- For each, write a one-sentence Strategic Result — what success
  looks like for that priority.

## Arrows

- 5-8 arrows total.
- Direction is FIXED: Capacity → Internal Process → Customer →
  Financial. Within-perspective arrows are allowed (e.g. between
  two Financial objectives like "decrease costs" → "increase
  profitability").
- Every arrow names a `hypothesis` — a one-sentence cause-effect
  claim. The hypothesis is what makes the arrow testable. Generic
  hypotheses ("X enables Y") are unacceptable; the hypothesis must
  reference the specific mechanism.

Examples of GOOD hypotheses:
- "Investing in associate training (O.P) enables friendly,
  knowledgeable in-store interactions (I1.4), which drives repeat
  visits (C3)."
- "Improving end-to-end process speed (I2.5) lowers operating cost
  per transaction, contributing to margin growth (F3)."

Examples of BAD hypotheses:
- "O.T enables I1.1." (no mechanism)
- "Better people produce better outcomes." (generic)

## What's Missing? Gaps

- 2-4 gaps.
- Each gap explains a strategic question the public-data analysis
  cannot answer authoritatively. The gap is an INVITATION to the
  deep-dive conversation, not a criticism of the company.
- Gap candidates come from:
  - LOW-confidence objectives (especially in Capacity)
  - Missing channel / dealer / partner relationships in Customer
    perspective
  - Missing K&N internal-process categories (e.g. no innovation
    objectives for a company claiming product leadership)
  - Vague published vision / mission
  - Absent or vague published values
  - Lack of measurable signal for important objectives
- Each gap has a `deepDiveFraming` sentence in the form: "A Vector
  Advisory deep-dive would [specific action]." The action MUST be
  specific enough that the prospect can see what they'd get.

## Examples

```json
{
  "strategicPriorities": [
    {
      "name": "Grow Through Foodservice",
      "result": "Best-in-class signature food and beverage platform across all day parts, driving same-store sales growth."
    },
    {
      "name": "Deliver Convenience and Value",
      "result": "Industry-leading customer perception of speed and value across the convenience-store experience."
    },
    {
      "name": "Expand Profitably",
      "result": "High-quantity, high-quality store growth in core and new markets at target IRRs."
    }
  ],
  "arrows": [
    {
      "from": "O.P",
      "to": "I1.4",
      "hypothesis": "Investing in associate training (O.P) enables associates to deliver the friendly, knowledgeable in-store experience the brand promises (I1.4)."
    },
    {
      "from": "I1.4",
      "to": "C3",
      "hypothesis": "A friendly, knowledgeable in-store experience (I1.4) directly drives the customer perception that 'associates show they really care' (C3)."
    },
    {
      "from": "C3",
      "to": "F2",
      "hypothesis": "Customers who feel cared for visit more frequently and spend more per visit, growing same-store revenue (F2)."
    }
  ],
  "whatsMissing": [
    {
      "id": "G1",
      "title": "Cultural commitments not published",
      "description": "The company has not published an explicit values or culture statement. Public materials show consistent language about customer focus and quality, but the underlying cultural commitments that would anchor the Organizational Capacity perspective are not visible to public-data analysis.",
      "deepDiveFraming": "A Vector Advisory deep-dive would interview leadership and frontline associates to articulate the working culture and translate it into Organizational Capacity objectives that connect to the strategy.",
      "relatedObjectiveIds": ["O.C"]
    },
    {
      "id": "G2",
      "title": "Channel-relationship strategy unclear",
      "description": "The company appears to sell through both direct retail and franchise / wholesale channels, but the strategic balance between them — and how they reinforce vs. compete — is not visible in public materials.",
      "deepDiveFraming": "A Vector Advisory deep-dive would map the channel economics and design Customer-perspective objectives for each channel to align incentives across the go-to-market.",
      "relatedObjectiveIds": ["C2"]
    }
  ]
}
```

Output JSON only. No prose around it.
