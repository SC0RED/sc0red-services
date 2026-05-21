Detail this AI opportunity for a PE portfolio company.

{company_context}

Opportunity: {opportunity_title}
{opportunity_description}

Provide the following fields:

1. **implementation_steps** — 3 specific implementation steps tied to this company.

2. **timeline** — one of "Quick Win (1-3 months)", "Medium-term (3-9 months)", or "Long-term (9-18 months)".

3. **investment_range** — one of "$50K-$100K", "$100K-$500K", "$500K-$1M", or "$1M+".

4. **roi_estimate** — one or two sentences of specific, company-grounded ROI rationale. Include a percentage figure somewhere in the prose (e.g., "30% reduction in support cost", "~25% lift in qualified pipeline"). The matching `roi_estimate_pct` numeric below must agree with this percentage.

5. **investment_value_usd** — an integer USD figure that lies INSIDE the `investment_range` bucket you picked in field 3. Default to the midpoint of that range; shade toward the low or high end only if the company context warrants it. **Examples:** `investment_range="$50K-$100K"` → `75000`. `"$100K-$500K"` → `300000`. `"$500K-$1M"` → `750000`. `"$1M+"` → use your judgment, but `1500000` is a safe default unless the company is clearly enterprise-scale. Emit `null` ONLY in the rare case where the dollar cost genuinely depends on a future negotiation or external trigger that you cannot bound — for almost every opportunity you'll have a defensible midpoint.

6. **roi_estimate_pct** — a number in the range `0..500` that matches the percentage figure in your `roi_estimate` prose above. **Examples:** prose says "30% reduction in support cost" → emit `30.0`. Prose says "doubles qualified pipeline" → emit `100.0`. Prose says "pays back in 12 months" → translate to annualised ROI (`100.0`). Values above 300 visually clamp on the chart with a caret marker; values above 500 are not accepted. Emit `null` ONLY when the prose genuinely doesn't quantify any return.

`null` is the EXCEPTION, not the default. The matrix renderer routes `null` rows to a footer strip rather than plotting them — that's the fallback for the rare unsizable opportunity, not a way to dodge an estimate. Default to a defensible number derived from your own string fields above.
