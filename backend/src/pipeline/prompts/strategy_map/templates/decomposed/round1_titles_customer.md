## Round 1 — Customer Perspective Titles

You are generating Step 4 of a strategy map. This call produces ONLY
the **list of customer-objective titles** (3 to 4 titles).
Definitions and panel classification come in a separate Round 2
call per title.

## Inputs

**Company name**: {company_name}
**Vision**: {vision_statement}
**Customer Value Proposition** (from Step 2): {value_proposition}
**Financial perspective objectives** (from Step 3, for downstream coherence):
{financial_objectives}

**Profile**:
{profile_summary}

**Top opportunities** (already classified):
{top_opportunities}

## Your task

Produce **3 to 4 short, imperative titles** for the customer
perspective. Each title must be voiced from the *customer's*
perspective ("I want…" / "I need…" framing in the implied subject)
when the panel is consumer; from the channel partner's perspective
when channel; from the partner's perspective when partner.

The customer perspective in K&N is split across panels:

- `consumer` — end-buyer / consumer.
- `channel` — distributor / reseller / retailer.
- `partner` — strategic partner, supplier, alliance.

For B2C-only companies most titles will be `consumer`. For B2B2C or
multi-tier distribution, expect a mix. Per the Vector house style,
use 1 channel/partner title at most when the value chain shows
meaningful indirect distribution.

Output JSON only:

```json
{
  "titles": [
    "<title 1, customer-voiced>",
    "<title 2, customer-voiced>",
    "<title 3, customer-voiced>",
    "<optional title 4>"
  ]
}
```

## Rules

- 3 or 4 titles, in priority order.
- Each title is a short customer-voiced phrase, 5-15 words.
- Titles MUST differentiate from each other.
- Do NOT include `id`, `definition`, `panel`, or any other fields.

## Example

```json
{
  "titles": [
    "Offer me fresh products in a friendly environment",
    "Recognise my loyalty and reward me appropriately",
    "Make my visit fast and convenient overall"
  ]
}
```

Output JSON only. No prose around it.
