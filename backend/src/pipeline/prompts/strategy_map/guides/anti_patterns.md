# Strategy Map Anti-Patterns

This guide catalogues the failure modes that make a strategy map look
credible at first glance but break down on a second read. The
generation MUST avoid every pattern listed below.

These anti-patterns are drawn from the Kaplan & Norton HBR article
("Having Trouble with Your Strategy? Then Map It", September–October
2000) and from accumulated consulting practice.

## Anti-pattern 1: the KPI scorecard illusion

**The trap**: producing a balanced list of metrics across the four
perspectives without articulating the cause-and-effect arrows that
connect them.

**What it looks like**:
- Financial: net profit, revenue growth, ROCE
- Customer: NPS, customer retention, market share
- Internal Process: defect rate, cycle time, on-time delivery
- Capacity: training hours, IT uptime, employee satisfaction

The list is "balanced" — every perspective has metrics — but there is
no STRATEGY. Why does training-hours improvement drive defect-rate
improvement? Why does defect-rate improvement drive customer
retention? Why does customer retention drive net profit? Without the
arrows, this is a stakeholder dashboard, not a strategy.

K&N: "Unless the link to strategy has been clearly thought through,
a KPI scorecard can be a dangerous illusion."

**How to avoid**: every objective in our generated map must connect
to at least one objective in an adjacent perspective via an arrow.
Step 7 of the generation chain (arrows + gaps) is where this is
enforced. If a generated objective has no arrows, it is removed.

## Anti-pattern 2: generic objectives ("customer satisfaction" alone)

**The trap**: titles that could appear on any company's strategy map.

**What it looks like**:
- "Improve customer satisfaction"
- "Increase employee engagement"
- "Drive operational excellence"
- "Be a great place to work"
- "Deliver value to shareholders"

These titles are technically valid but say nothing about THIS specific
company. They are placeholders that look like objectives.

**How to avoid**: every objective must be specific to the analysed
company's positioning, business model, customer value proposition, or
industry context. Generic placeholders are NEVER acceptable, even at
LOW confidence. A generic-sounding objective is worse than an absent
one — it gives the appearance of strategy without the substance.

When an obvious generic objective seems necessary (e.g. "Improve
customer satisfaction" for any service business), rewrite it to
specify HOW or for WHOM:

✗ "Improve customer satisfaction"
✓ "Improve mid-tier subscription customers' onboarding experience"
✓ "Reduce response-to-resolution time for enterprise support tickets"

If sufficient public data isn't available to make the objective
specific, OMIT IT and surface as a "What's Missing?" gap instead.

## Anti-pattern 3: missing channel / dealer / partner relationships

**The trap**: a Customer perspective populated with end-user
objectives only, when the company actually sells through intermediaries.

**Mobil case study (HBR)**: senior management noticed that one
business unit had no objectives or metrics for dealers. Mobil's
go-to-market is via independent franchised dealers; without dealer-
relationship objectives, the strategy map missed a strategically
critical layer.

**How to avoid**: in the Customer perspective generation step, check
the company's go-to-market model:

- Direct B2C? End-user objectives only is fine.
- B2B with sales team? Direct customer objectives, but consider
  named-account or vertical-segment structure.
- Through distributors / dealers / resellers? At LEAST one objective
  about the channel relationship is required. Often this is its own
  Customer-perspective sub-section ("Win-Win Dealer Relations" in the
  Mobil case).
- Marketplace / platform? Both sides of the market need objectives
  (e.g. an Airbnb-style platform needs Host objectives and Guest
  objectives).

If the company's go-to-market involves channels but the public data
doesn't support specific channel-relationship objectives, surface as
a gap.

## Anti-pattern 4: missing quality measures

**Mobil case study (HBR)**: a different business unit had no measure
for product quality. Either the unit had quietly dropped quality as a
strategic priority (likely a mistake), or it was so confident in its
quality that it didn't track it (also a mistake).

**How to avoid**: any company claiming Operational Excellence as its
value proposition MUST have a quality-related Internal Process
objective. Any company in a regulated industry (food, healthcare,
financial services, pharma) MUST have at least one quality or
compliance objective. If not present in public materials, surface as
a gap.

## Anti-pattern 5: vanity vision statements

**The trap**: visions that are aspirational but not directional.

**What it looks like**:
- "To be the leading provider of innovative solutions that delight
  customers and create lasting value."
- "Empowering people to achieve their best."
- "A world transformed by [our product category]."

These are interchangeable across companies. They give no clue what
the company actually does, who it serves, or how it differs.

**How to avoid**: a good vision statement names AT LEAST one of the
following:
- A specific customer segment ("for commuters", "for mid-market PE")
- A specific outcome ("reduce time-to-onboarding to under 24 hours")
- A specific industry position ("the most appetising convenience
  retailer", "the lowest-cost producer of ingot")
- A specific geographic reach ("the U.S. mid-Atlantic", "Latin
  America's leading…")

If the company's published vision is vanity-grade, generate a more
specific vision FROM public materials and mark the original as a gap
("Public vision is vanity-grade; the deep-dive would refine it
toward specificity").

## Anti-pattern 6: lists of metrics without arrows

(See anti-pattern 1 — this is the same trap restated as a check on
arrow generation.)

When generating Step 7 (arrows + gaps), confirm that:
- Every Internal Process objective has at least one arrow to a
  Customer or Financial objective.
- Every Capacity objective has at least one arrow to an Internal
  Process objective.
- Every Customer objective has at least one arrow to a Financial
  objective.

Objectives without arrows are removed (they fail the strategy-map
test) or surfaced as gaps ("This objective wasn't connected to a
financial outcome — worth a deep-dive on its causal chain").

## Anti-pattern 7: confusing themes with objectives

**The trap**: putting a theme name in the Internal Processes
perspective as if it were an objective.

✗ "Grow Through Foodservice" as an Internal Process objective.
   (This is a THEME — a grouping label.)
✓ "Develop fresh food and beverage offers that satisfy needs across
   all day parts" as an Internal Process objective UNDER the theme
   "Grow Through Foodservice".

Themes are headers. Objectives are the action items inside them.
Generation Step 5 (Internal Processes) outputs both: 2-3 themes AND
4-6 objectives bucketed under those themes. Don't confuse the levels.

## Anti-pattern 8: customer perspective in third person

**The trap**: writing customer objectives as descriptions of the
company's intent, not as the customer's voice.

✗ "Wawa offers fresh food in clean stores."  (third person, company POV)
✓ *"Offer fresh and inviting food and beverages that meet my needs in
   a pleasant environment."*  (first person, customer POV — note the
   quotation marks)

The Vector house style requires first-person customer voice with
quotation marks. (See `vector_style_guide.md`.) This is a stylistic
choice, but it's load-bearing — it's what makes Vector-style maps
recognisable.

## Anti-pattern 9: capacity perspective ignored

**The trap**: shipping a strategy map where the Organizational
Capacity perspective contains only generic placeholders ("Develop our
people", "Build our technology") without specifics.

K&N: "Although executive teams readily acknowledge the importance of
the learning and growth perspective, they generally have trouble
defining the corresponding objectives."

**How to avoid**: every Capacity objective must name a specific
capability the company needs FOR ITS STRATEGY. Generic capacity
objectives are worse than no capacity objectives — they mask the gap
without filling it.

For public-data analysis: tech-stack signals (job postings,
engineering blog), about-us / leadership pages, careers pages, and
Glassdoor are useful sources. If those don't yield specifics for one
of the three buckets (People / Technology / Culture), set the
objective to LOW confidence and surface as a gap.

## Anti-pattern 10: arrows running the wrong direction

The causality direction is FIXED:

```
Capacity → Internal Process → Customer → Financial
```

NOT:
```
Financial → Customer  (financial pressure does not directly
                       cause customer outcomes)
Customer → Internal Process  (customer behaviour does not directly
                              cause process improvement)
```

Within-perspective arrows are allowed (e.g. within Financial:
"decrease operating costs" → "increase profitability").

Step 7 of the generation chain validates arrow directions.
Generated arrows that violate the canonical direction are flagged
and corrected.
