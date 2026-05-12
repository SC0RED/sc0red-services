## Value Proposition: Secondary Classifier (decomposed)

You are classifying the company's SECONDARY customer value proposition.

This call always runs, but its result is only used by the strategy map
when the parallel primary-classifier call returns `hybrid`. Treat your
answer as the choice you'd make IF the primary classification is
`hybrid` — i.e. which secondary proposition would be co-pursued
alongside the dominant one.

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

Pick ONE of three (NOT `hybrid` — secondary cannot itself be hybrid):

- `operational_excellence`
- `customer_intimacy`
- `product_leadership`

Produce JSON with exactly ONE field:

```json
{
  "secondary": "<one of: operational_excellence | customer_intimacy | product_leadership>"
}
```

## Rules

- Pick the second-strongest proposition signal you see in the inputs.
- Even if you think the primary is single-proposition (not hybrid),
  pick the best secondary candidate — the assembly layer will discard
  it unless primary == hybrid.

## Examples

```json
{ "secondary": "operational_excellence" }
```

```json
{ "secondary": "customer_intimacy" }
```

Output JSON only. No prose around it.
