## Step 4 — Customer Perspective Objectives (first-person customer voice)

You are generating Step 4 of a 7-step strategy map. This step produces
3-4 Customer perspective objectives, written in first-person customer
voice per the Vector Advisory house style.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition** (from Step 2): {value_proposition}
**Mission**: {mission_statement}

**Scraped content** (about-us, customer testimonials, case studies):
{scraped_content}

**Customer-experience signals**:
- Risk scores (focus on customer_behavior, competitive_displacement):
  {customer_risk_signals}
- Opportunities with `value_lever: "Revenue Side"`:
  {revenue_opportunities}

**Channel / go-to-market** (inferred from opportunities and scraped
content):
{go_to_market_signal}

## Your task

Produce 3-4 Customer perspective objectives. Each MUST be written as
a first-person customer voice quote. Anchor to the value proposition
classification.

If the company sells through dealers / distributors / marketplaces
(channel-mediated go-to-market), include AT LEAST ONE additional
objective covering the channel relationship — a missing channel
objective is one of the K&N anti-patterns from the Mobil case.

Produce JSON:

```json
{
  "customer": {
    "objectives": [
      {
        "id": "C1",
        "title": "<first-person customer quote, no surrounding quote marks in JSON>",
        "definition": "<continued first-person customer voice paragraph, 50-150 words>",
        "panel": "<one of: consumer | channel | partner>",
        "confidence": "<HIGH | MEDIUM | LOW>",
        "rationale_source": "<short note on which input grounds this>"
      },
      ...
    ]
  }
}
```

## Rules

- 3-4 objectives total.
- IDs are C1, C2, C3, [C4] in order.
- Titles are first-person quotes from the customer's perspective.
  Quotation marks are added by the renderer; do not include them in
  the JSON `title` value. The JSON title MUST start with a verb-led
  phrase a customer would use ("Offer me…", "Help me…", "Provide me
  with…", "Show me you really care…").
- Definitions continue in first-person customer voice. Length 50-150
  words. Reference specific scraped signals where possible.
- `panel` segments the objective by customer type. Most objectives
  are `consumer`. If the company has dealers / distributors, those
  objectives are `channel`. If the company is a marketplace with
  two sides, the supply-side objectives are `partner`.
- For value proposition `customer_intimacy`, lean toward Service /
  Relationship / Image attributes (per K&N's Customer-perspective
  exhibit on page 6 of the HBR article). For
  `operational_excellence`, lean toward Product/Service Attributes
  (price, time, quality, selection). For `product_leadership`,
  lean toward Functionality / Performance / Best-in-class image.
- `confidence` per the rules in the system prompt.

## Example (from Wawa exemplar)

```json
{
  "customer": {
    "objectives": [
      {
        "id": "C1",
        "title": "Offer fresh and inviting food and beverages that meet my needs in a pleasant environment",
        "definition": "Wawa is my preferred destination for on-the-go breakfast, beverages, lunch, dinner and snacks. I choose Wawa because of the signature products, excellent in-store shopping experience and a store that looks good inside and out. I am a fan of the brand, and passionately recommend Wawa to others.",
        "panel": "consumer",
        "confidence": "HIGH",
        "rationale_source": "Verbatim from the company's customer testimonials and signature-product positioning."
      }
    ]
  }
}
```

Output JSON only. No prose around it.
