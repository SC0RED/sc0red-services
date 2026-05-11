## Value Proposition: Exemplar Company (decomposed)

You are producing ONLY the famous-exemplar company that illustrates
this company's customer value proposition.

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

Name a well-known brand exemplar that illustrates the SAME value
proposition the company under analysis pursues. The exemplar gives
the reader an immediate "ah, like X" anchor.

Produce JSON with exactly ONE field:

```json
{
  "exemplar_company": "<a famous brand name, optionally with a short context phrase>"
}
```

## Rules

- Pick a brand the reader will instantly recognise.
- Maximum 100 characters. Short and crisp.
- Single brand preferred; if a contextual phrase clarifies it (e.g.
  "Mobil North American Marketing & Refining (per the K&N HBR 2000
  case)"), include it.
- If the company under analysis IS itself a household name, pick a
  related peer rather than the company itself.

## Examples

```json
{ "exemplar_company": "Mobil North American Marketing & Refining (per the K&N HBR 2000 case)" }
```

```json
{ "exemplar_company": "Intel" }
```

```json
{ "exemplar_company": "Home Depot" }
```

Output JSON only. No prose around it.
