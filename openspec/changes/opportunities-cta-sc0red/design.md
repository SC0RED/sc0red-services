## Context

Current rendering in `OpportunitiesList.tsx` (lines 319-347) and the PDF export route:

```
Opportunity card (expanded)
├─ Description
├─ Implementation Steps (numbered)
├─ [Investment] [ROI]  (two-column grid)
└─ "Implementation Partners" row
    └─ badge badge-neutral × N  ← neutral gray pills
```

Same block exists in `frontend/src/app/api/export/pdf/[analysisId]/route.ts` (lines 145-152) with `.vendor-chip` styling.

The `related_services` field comes from the backend pipeline (`detail.json` schema: "Up to 3 relevant vendor or service names"). Nothing about this data needs to change — the issue is purely presentation.

## Goals / Non-Goals

**Goals:**
- Reposition sc0red as *the* implementation partner, not one of many
- Place the sc0red pitch at the point of maximum reader interest — after they've read the opportunities, before they close the tab
- Keep the pitch discoverable but not noisy (a single placement, not per-card)
- Mirror the treatment in the PDF export so printed artifacts carry the same framing
- Keep the contact URL easy to rotate (env-configurable)

**Non-Goals:**
- Modifying backend pipeline output or schemas
- Click analytics (separate proposal)
- Per-opportunity CTA (explicitly rejected — too noisy)
- Redesigning the opportunity cards themselves

## Decisions

### 1. Bottom placement, not top

**Decision: The sc0red banner sits at the **bottom** of the opportunities list, after the last opportunity card.**

Top placement (before the cards) pitches before the reader has built up interest — the CTA lands cold. Bottom placement follows the natural reading arc:

```
What opportunities exist?  →  What does each one cost/return?  →  WHO BUILDS THIS?
      (the cards)                  (per-card detail)               (sc0red banner)
```

By the time the reader reaches the banner, they've seen every opportunity. They've either been convinced or they haven't — either way, the CTA lands with full context.

### 2. Single banner, not per-card

**Decision: One CTA at the bottom of the list, not a hook on each card.**

We considered a per-card "sc0red implements this →" line in the collapsed header (always visible, maximum touchpoints). Rejected because:

- A scan with 15 opportunities would show 15 CTAs on screen at once — reads as spam
- Each per-card CTA would need its own copy variant to feel varied, or identical copy that reads repetitive
- The CTA has nothing opportunity-specific to say beyond "we build this" — the sc0red value prop is holistic, not per-opportunity

A single well-placed banner carries more weight than 15 muted ones.

### 3. Expandable, collapsed by default

**Decision: The banner renders collapsed by default, with a chevron to expand into the full pitch.**

```
Collapsed (default):
┌──────────────────────────────────────────────────────────┐
│  ◆  sc0red can help you capture these opportunities   ▾ │
└──────────────────────────────────────────────────────────┘

Expanded:
┌──────────────────────────────────────────────────────────┐
│  ◆  sc0red can help you capture these opportunities   ▴ │
│                                                          │
│  Our AI specialists implement opportunities like these   │
│  from strategy through production deployment —           │
│  typically in 60–90 days.                                │
│                                                          │
│  [  Start the conversation →  ]                          │
└──────────────────────────────────────────────────────────┘
```

Rationale:
- Collapsed-by-default keeps the page visually clean and doesn't make the banner feel salesy
- The single collapsed line is enough to plant the association ("sc0red = can help with this") for readers who don't expand
- Readers who engage get a fuller pitch + a clear next step

Accessibility: follows the same `aria-expanded` + `aria-controls` pattern the opportunity cards already use.

### 4. Tech Stack relabel, vendor chips retained

**Decision: Rename the per-card "Implementation Partners" section to "Tech Stack" and keep the vendor chips as-is.**

The vendor names (Datadog, Salesforce, Veeva, etc.) are useful context — they signal technical realism. But labeled "Implementation Partners" they imply those vendors do the implementing. Under "Tech Stack" they read as "the tools a real build would touch" — credibility without competing with sc0red for the partner framing.

No visual changes to the chips themselves. Only the heading text changes, in both the React component and the PDF export.

### 5. Env-configurable CTA URL

**Decision: Read the contact URL from `NEXT_PUBLIC_SC0RED_CONTACT_URL`, default to `https://www.sc0red.com/contact`.**

- `NEXT_PUBLIC_*` makes it available in client-side code (the banner is a client component)
- Default constant means no deploy-time configuration is required for it to work
- Trivial to swap to a Calendly link, a different domain, or an internal routing URL later by setting the env var

**Scope note:** This PR wires the resolver at the Next.js code level only. Per-environment override at the CDK / Amplify branch level (so staging can point elsewhere than production) is a fast-follow task. The Amplify build spec already greps for `NEXT_PUBLIC_*` into `.env.production`, but `amplify_construct.py::create_branch()` does not currently inject this variable — so the default is used for all deployed builds today. That's fine: the default IS the production URL. Only when we want to diverge per environment do we need the CDK wiring.

### 6. PDF export: static, non-interactive, same messaging

**Decision: The PDF renders the expanded state inline (no collapse), with the same copy and the contact URL printed as a visible link.**

Rationale:
- PDFs are artifacts people share inside a firm — the printed CTA should stand on its own without requiring a click
- Printing a "[Learn more ▾]" affordance in a PDF would be confusing (no click in print)
- The URL should be visible text, not a hidden `href`, so recipients of a printed copy can type it

Per-card vendor chips keep their existing `.vendor-chip` styling, only the heading text changes to "Tech Stack".

### 7. Banner visibility tied to `filteredOpps.length > 0`

**Decision: The banner only renders when at least one opportunity is visible in the current filter.**

If the user filters to a lever (Revenue / Cost / Both) and the filter returns zero results, we don't show a sc0red CTA pitching about "these opportunities" when there aren't any. The component already tracks `filteredOpps` — gate on that.

## Risks / Trade-offs

- **Copy tone.** The recommended copy ("sc0red delivers this. Our AI specialists implement opportunities like this from strategy through production — typically in 60–90 days.") makes a specific time claim. If 60–90 days isn't a commitment we can make, soften to "in a matter of weeks" or drop the timeline. The proposal ships with conservative copy; a final copy review with whoever owns marketing is a task item.
- **Env var fallback silently hides misconfiguration.** If `NEXT_PUBLIC_SC0RED_CONTACT_URL` is set to an empty string, the banner's link would be a broken `href=""`. Mitigation: the component treats any falsy env value as "use default" rather than honoring an empty string. Documented in `.env.local.example`.
- **PDF inline URL readability.** Rendering a full URL as visible text (`https://www.sc0red.com/contact`) can look ugly in a printed doc. Mitigation: print it on its own line in a subdued color, not inline with pitch copy.
- **Future per-card variant.** If we ever want per-card CTAs (e.g., "request sc0red to spec this one opportunity"), the banner-only shape here doesn't block it — it just chooses not to go there today. Future work can add per-card hooks without reshaping the banner.
