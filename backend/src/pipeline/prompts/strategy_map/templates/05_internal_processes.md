## Step 5 — Internal Processes Perspective (themed)

You are generating Step 5 of a 7-step strategy map. This step produces
4-6 Internal Processes objectives organised into 2-3 named themes,
per the Vector Advisory house style.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition** (from Step 2): {value_proposition}
**Financial objectives** (from Step 3): {financial_objectives}
**Customer objectives** (from Step 4): {customer_objectives}

**Value chain analysis** (already produced by Janus):
{value_chain}

**Opportunities** (with strategic_category and value_lever):
{opportunities}

**Risk scores** (especially margin_compression, supply_chain,
regulatory_compliance):
{operational_risk_signals}

## Your task

Produce 4-6 Internal Processes objectives, GROUPED into 2-3 named
themes. Themes connect to the Financial perspective's revenue or
productivity strategies — readers should be able to trace each theme
to a financial outcome.

Produce JSON:

```json
{
  "internalProcesses": {
    "themes": [
      {
        "name": "<verb-led 2-5 word theme name>",
        "supports_financial_objectives": ["F1", "F2"],
        "objectives": [
          {
            "id": "I1.1",
            "title": "<imperative title, e.g. 'Develop fresh food and beverage offers across all day parts'>",
            "definition": "<50-150 word 'We will…' definition>",
            "category": "<one of: innovation | customer_management | operational_excellence | citizenship>",
            "confidence": "<HIGH | MEDIUM | LOW>",
            "rationale_source": "<short note>"
          }
        ]
      }
    ]
  }
}
```

## Rules

- 2-3 themes. Theme names are verb-led (Grow…, Deliver…, Expand…,
  Build…). 2-5 words each.
- 4-6 objectives total across all themes.
- Objective IDs follow `I{theme_index}.{objective_index}` pattern
  (e.g. I1.1, I1.2, I2.1, I3.1).
- Each theme's `supports_financial_objectives` array names the F-IDs
  it helps achieve. This is the connector that makes themes
  meaningful — a theme that doesn't support any financial objective
  is suspicious.
- `category` tags each objective with one of the K&N four
  internal-process categories. Coverage across multiple categories
  indicates a balanced strategy; gaps may signal blind spots that
  should surface in the gap panel later.
- Definitions are 50-150 words, "We will…" voice. Name specific
  initiatives where possible (referencing the value chain or
  opportunities).
- For value proposition `operational_excellence`, themes should lean
  toward operations / cost / cycle-time. For `customer_intimacy`,
  toward customer-management / experience / loyalty. For
  `product_leadership`, toward innovation / R&D / time-to-market.
  Hybrid cases need themes covering both sides.

## Example (Wawa-style)

```json
{
  "internalProcesses": {
    "themes": [
      {
        "name": "Grow Through Foodservice",
        "supports_financial_objectives": ["F1", "F2"],
        "objectives": [
          {
            "id": "I1.1",
            "title": "Develop fresh food and beverage offers that satisfy needs across all day parts",
            "definition": "We have made great strides in developing a compelling, quality food and beverage offer that represents value to our customers. We must now create and improve the offer to meet customer needs across all day parts, especially dinner. We will protect and grow core categories by staying abreast of market and consumer trends, innovating products and platforms, and creating signature offerings.",
            "category": "innovation",
            "confidence": "HIGH",
            "rationale_source": "Top opportunity #2 (foodservice expansion) and value-chain emphasis on category innovation."
          }
        ]
      },
      {
        "name": "Deliver Convenience and Value",
        "supports_financial_objectives": ["F2", "F3"],
        "objectives": [...]
      }
    ]
  }
}
```

Output JSON only. No prose around it.
