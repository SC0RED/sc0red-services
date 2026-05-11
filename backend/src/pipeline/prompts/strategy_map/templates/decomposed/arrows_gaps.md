## "What's Missing?" Gaps (decomposed)

You are generating ONLY the strategic gaps — the "What's Missing?"
deep-dive conversation starters. Arrows and priorities are handled by
separate parallel calls — do not include them here.

## Inputs

**Vision**: {vision_statement}
**Customer Value Proposition**: {value_proposition}

**Financial objectives**: {financial_objectives}
**Customer objectives**: {customer_objectives}
**Internal Processes themes**: {internal_processes}
**Organizational Capacity**: {organizational_capacity}
**Confidence markers**: {confidence_summary}

## Your task

Produce JSON with 2-4 strategic gaps. Each gap is a strategic question
the public-data analysis CANNOT answer authoritatively — an invitation
to the deep-dive conversation, not a criticism of the company.

```json
{
  "whatsMissing": [
    {
      "id": "G1",
      "title": "<short gap label, 4-100 characters>",
      "description": "<1-2 sentences, 30-600 characters, explaining why public-data analysis cannot resolve this gap>",
      "deepDiveFraming": "<1 sentence, 30-400 characters, in the form 'A Vector Advisory deep-dive would [specific action].'>",
      "relatedObjectiveIds": ["<optional list of objective IDs the gap touches>"]
    }
  ]
}
```

## Rules

- 2-4 gaps total.
- Gap IDs are G1, G2, G3, G4 in priority order.
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
- `relatedObjectiveIds` should be populated when the gap touches one
  or more specific objectives by ID.

## Example

```json
{
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
