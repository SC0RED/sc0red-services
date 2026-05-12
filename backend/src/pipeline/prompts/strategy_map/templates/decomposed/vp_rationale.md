## Value Proposition: Rationale (decomposed)

You are producing ONLY the one-to-two-sentence rationale justifying the
company's value-proposition classification.

This call runs in parallel with the primary, secondary, and exemplar
calls. You do not see their outputs — judge from the same inputs they
have.

## Inputs

**Company name**: {company_name}
**Industry**: {industry}

**Vision**: {vision_statement}
**Mission**: {mission_statement}

**Scraped content** (about-us, products, customer testimonials):
{scraped_content}

**Opportunity strategic categories**: {opportunity_categories}

**Value chain emphasis**: {value_chain_summary}

## Your task

Write the rationale sentence(s) justifying the company's primary
value-proposition classification. You may write the rationale
treating any of the four propositions as the answer — the assembled
output will pair your rationale with the parallel primary-classifier's
choice, so write the rationale that fits the strongest signal you see.

Produce JSON with exactly ONE field:

```json
{
  "rationale": "<one or two sentences, 20-600 characters>"
}
```

## Rules

- The rationale MUST refer to at least one specific signal from the
  inputs (a specific opportunity category, a specific scraped phrase,
  a specific value-chain activity). No hand-waving.
- Reference concrete inputs, not generic claims.
- 20-600 characters.

## Examples

```json
{
  "rationale": "Public materials emphasise customer experience (clean stores, friendly associates, signature products) AND operational efficiency (industry-leading cost per unit). Neither customer intimacy nor operational excellence alone explains the strategy."
}
```

```json
{
  "rationale": "Company positions explicitly on technical performance (e.g. fastest, most powerful, highest-precision) in scraped product copy and the opportunity categories are dominated by 'Competitive Moat' (4 of 5 opportunities)."
}
```

Output JSON only. No prose around it.
