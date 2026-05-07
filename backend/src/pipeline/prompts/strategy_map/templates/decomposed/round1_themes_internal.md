## Round 1 — Internal Processes Themes

You are generating Step 5 of a strategy map. Internal Processes
objectives are GROUPED into 2-3 named themes per the Vector
Advisory house style. This call produces ONLY the **theme list**
plus each theme's `supports_financial_objectives` mapping.
Per-theme objective titles come in Round 2; per-objective
elaboration comes in Round 3.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition**: {value_proposition}
**Financial objectives**: {financial_objectives}
**Customer objectives**: {customer_objectives}

**Value chain analysis**:
{value_chain}

**Opportunities** (with strategic_category and value_lever):
{opportunities}

## Your task

Produce **2-3 themes**, each with:

- a verb-led 2-5 word `name` (e.g. "Differentiate the offer",
  "Improve operational throughput")
- a list of which financial-perspective IDs (F1/F2/F3) this theme
  supports — at least one ID, can include multiple

Output JSON:

```json
{
  "themes": [
    {
      "name": "<verb-led 2-5 word theme name>",
      "supports_financial_objectives": ["F1"]
    },
    {
      "name": "<another theme>",
      "supports_financial_objectives": ["F2", "F3"]
    }
  ]
}
```

## Rules

- Exactly 2 or 3 themes.
- Each theme's `name` is verb-led, 2-5 words. No punctuation.
- `supports_financial_objectives` MUST contain at least one ID from
  {F1, F2, F3} — the financial IDs are positional.
- Themes must be NON-OVERLAPPING — readers should be able to assign
  any internal-process objective to exactly one theme.
- Do NOT include `objectives` in the response — that comes in Round 2.

## Example

```json
{
  "themes": [
    {
      "name": "Differentiate the offer",
      "supports_financial_objectives": ["F1"]
    },
    {
      "name": "Improve operational throughput",
      "supports_financial_objectives": ["F2"]
    }
  ]
}
```

Output JSON only. No prose around it.
