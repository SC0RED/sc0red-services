## Step 2 — Customer Value Proposition Classification

You are generating Step 2 of a 7-step strategy map. This step
classifies the company's customer value proposition. The output
anchors every downstream perspective generation.

## Inputs

**Company name**: {company_name}
**Industry**: {industry}

**Vision (from Step 1)**: {vision_statement}
**Mission (from Step 1)**: {mission_statement}

**Scraped content** (about-us, products, customer testimonials):
{scraped_content}

**Opportunity strategic categories** (already classified by Janus):
{opportunity_categories}

**Value chain emphasis** (which activities are most opportunity-rich):
{value_chain_summary}

## Your task

Classify the company's primary Customer Value Proposition as ONE of:

- `operational_excellence` — best price, best speed, best on-time
  delivery (e.g. McDonald's, Dell, Walmart, Costco)
- `customer_intimacy` — best relationship, best solution-fit, best
  service (e.g. Home Depot, Nordstrom, IBM 1960s–70s)
- `product_leadership` — best functionality, best features,
  best-in-class performance (e.g. Intel, Sony, Apple, NVIDIA)
- `hybrid` — when two propositions are clearly co-pursued and the
  company would lose its identity without either (Mobil-style:
  customer intimacy + operational excellence)

Produce JSON:

```json
{
  "primary": "<one of: operational_excellence | customer_intimacy | product_leadership | hybrid>",
  "secondary": "<one of the same, or null>",
  "rationale": "<one or two sentences justifying the classification>",
  "exemplar_company": "<a brand exemplar that illustrates this proposition for context>"
}
```

## Rules

- `secondary` is required ONLY when `primary` is `hybrid`. Set to
  `null` for single-proposition cases.
- The `rationale` MUST refer to at least one specific signal from
  the inputs (a specific opportunity category, a specific scraped
  phrase, a specific value-chain activity). No hand-waving.
- Hybrid is acceptable when warranted but is also a hallucination
  risk — the AI may default to "hybrid" when undecided. Use it
  ONLY when neither single proposition genuinely fits. If you can
  pick one, pick one.

## Examples

```json
{
  "primary": "hybrid",
  "secondary": "operational_excellence",
  "rationale": "Public materials emphasise customer experience (clean stores, friendly associates, signature products) AND operational efficiency (industry-leading cost per unit, refinery-yield improvements). Neither customer intimacy nor operational excellence alone explains the strategy.",
  "exemplar_company": "Mobil North American Marketing & Refining (per the K&N HBR 2000 case)"
}
```

```json
{
  "primary": "product_leadership",
  "secondary": null,
  "rationale": "Company positions explicitly on technical performance (e.g. fastest, most powerful, highest-precision) in scraped product copy and the opportunity categories are dominated by 'Competitive Moat' (4 of 5 opportunities).",
  "exemplar_company": "Intel"
}
```

Output JSON only. No prose around it.
