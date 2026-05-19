## Value Proposition: Primary Classifier (decomposed)

You are classifying the company's PRIMARY customer value proposition.
This is one of four parallel calls that together produce the value-
proposition record; you do not see the other calls' outputs.

## Inputs

**Company name**: {company_name}
**Industry**: {industry}

**Vision** (from Step 1, may say "(unknown)" if not yet generated):
{vision_statement}

**Mission** (from Step 1, may say "(unknown)" if not yet generated):
{mission_statement}

**Scraped content** (about-us, products, customer testimonials):
{scraped_content}

**Opportunity strategic categories** (already classified by the analysis pipeline):
{opportunity_categories}

**Value chain emphasis** (which activities are most opportunity-rich):
{value_chain_summary}

## Your task

Classify the company's primary Customer Value Proposition as ONE of:

- `operational_excellence` — best price, best speed, best on-time
  delivery (e.g. McDonald's, Dell, Walmart, Costco)
- `customer_intimacy` — best relationship, best solution-fit, best
  service (e.g. Home Depot, Nordstrom, IBM 1960s–70s)
- `product_leadership` — best functionality, best features, best-in-
  class performance (e.g. Intel, Sony, Apple, NVIDIA)
- `hybrid` — when two propositions are clearly co-pursued and the
  company would lose its identity without either (Mobil-style:
  customer intimacy + operational excellence)

Produce JSON with exactly ONE field:

```json
{
  "primary": "<one of: operational_excellence | customer_intimacy | product_leadership | hybrid>"
}
```

## Rules

- Hybrid is acceptable when warranted but is also a hallucination
  risk — pick `hybrid` ONLY when neither single proposition genuinely
  fits. If you can pick one, pick one.
- The rationale and exemplar fields are NOT your job — separate calls
  handle them.

## Examples

```json
{ "primary": "hybrid" }
```

```json
{ "primary": "product_leadership" }
```

Output JSON only. No prose around it.
