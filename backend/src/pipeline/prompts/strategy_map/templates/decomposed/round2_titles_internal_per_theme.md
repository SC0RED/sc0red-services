## Round 2 — Internal-Processes Theme Objective Titles

You are elaborating ONE internal-processes theme's **list of
objective titles**. Per-objective elaboration (definition,
category, confidence) comes in Round 3.

## Inputs

**Company name**: {company_name}
**Customer Value Proposition**: {value_proposition}

**This theme's name**: {theme_name}
**This theme supports financial objectives**: {supports_financial_objectives}
**Sibling theme names** (for differentiation):
{sibling_theme_names}

**Value chain analysis**:
{value_chain}

**Opportunities**:
{opportunities}

## Your task

Produce **1 to 4 objective titles** that fall under this theme.
Each title is a short imperative phrase.

Output JSON:

```json
{
  "titles": [
    "<title 1>",
    "<title 2>",
    "<optional title 3>",
    "<optional title 4>"
  ]
}
```

## Rules

- 1 to 4 titles.
- Each title is a short imperative phrase, 5-15 words. No buzzwords.
- All titles must fit cleanly under the theme name above (no
  off-theme objectives).
- Titles must NOT overlap with the sibling theme names listed above.
- Do NOT include `id`, `definition`, `category`, or any other fields.

## Example

For theme "Differentiate the offer":

```json
{
  "titles": [
    "Develop signature fresh-food offers",
    "Refresh store ambience and merchandising"
  ]
}
```

Output JSON only. No prose around it.
