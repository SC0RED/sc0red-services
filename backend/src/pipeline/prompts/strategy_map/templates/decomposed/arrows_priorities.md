## Strategic Priorities (decomposed)

You are generating ONLY the strategic priorities for the strategy map's
top header band. Arrows and gaps are handled by separate parallel
calls — do not include them here.

## Inputs

**Vision**: {vision_statement}
**Customer Value Proposition**: {value_proposition}

**Financial objectives**: {financial_objectives}
**Customer objectives**: {customer_objectives}
**Internal Processes themes**: {internal_processes}
**Organizational Capacity**: {organizational_capacity}

## Your task

Produce JSON with the strategic priorities. Priorities map 1:1 to the
Internal Processes themes — reuse the theme NAMES verbatim from the
internal-processes input.

```json
{
  "strategicPriorities": [
    {
      "name": "<exact theme name from internal_processes>",
      "result": "<one-sentence strategic-result statement, 20-300 characters>"
    }
  ]
}
```

## Rules

- Use the theme names verbatim from the internal-processes input.
  The count matches (2-3 priorities = 2-3 themes).
- For each, write a one-sentence Strategic Result — what success
  looks like for that priority.
- Strategic Result is specific and outcome-focused, not aspirational.
  Example: "Industry-leading customer perception of speed and value
  across the convenience-store experience" — names the metric (speed,
  value perception) and the scope (convenience-store experience).

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
  ]
}
```

Output JSON only. No prose around it.
