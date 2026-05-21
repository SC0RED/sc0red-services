Detail this AI opportunity for a PE portfolio company.

{company_context}

Opportunity: {opportunity_title}
{opportunity_description}

Provide the following fields:

1. **implementation_steps** — 3 specific implementation steps tied to this company.

2. **timeline** — one of "Quick Win (1-3 months)", "Medium-term (3-9 months)", or "Long-term (9-18 months)".

3. **investment_range** — one of "$50K-$100K", "$100K-$500K", "$500K-$1M", or "$1M+".

4. **roi_estimate** — one or two sentences of specific, company-grounded ROI rationale.

5. **investment_value_usd** — the total estimated USD cost to implement the opportunity end-to-end over the next 12-24 months. **Include** software licences, integration cost, dedicated headcount fraction × salary, and opportunity cost of redirected effort. Emit an integer (no decimals, no commas — e.g. `120000` not `"$120K"`). **If you cannot ground a number in the company context above, emit `null`** — `null` is strictly preferred over a hallucinated guess. The matrix renderer routes `null` rows to a separate "uncalibrated" strip rather than plotting them with bogus coordinates, so honest `null` is more useful than a confident wrong number.

6. **roi_estimate_pct** — the estimated ROI percentage as a number in the range `0..500`. Computed as `(annualised_value_created - annualised_cost) / annualised_cost * 100`. A 50% ROI means the opportunity returns 1.5x its cost in year one. Values above 300 will visually clamp on the chart; values above 500 are not accepted by the schema. **If you cannot ground a number in the company context, emit `null`.** Same null-preferred-over-guess rule as above.

Both numeric fields are nullable independently — it is fine to emit one number and one `null` if you can size only one axis. The string `investment_range` and prose `roi_estimate` fields above stay populated regardless.
