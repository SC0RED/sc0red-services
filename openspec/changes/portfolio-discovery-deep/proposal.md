## Why

**Status: exploratory — proposal only. Do not implement without further design review.**

After `raise-discovery-recall` (Levers 1-4) lands, portfolio discovery recall should jump from ~50% to ~85-95% on WordPress-style PE sites like perotjain.com. However, a class of PE websites remains where the quick-win levers won't help:

- **Non-WordPress CMSes with weird DOM structures** — bespoke React or custom HTML where no single CSS pattern repeats; heuristic link walking misses the shape.
- **JavaScript-rendered portfolios** — pages where the company grid is injected client-side (common on modern VC sites, some PE groups). Our `httpx` + `BeautifulSoup` scraper never sees the companies at all.
- **Sites with structured data (JSON-LD) that we currently ignore** — some sites publish `Organization` or `ItemList` schema.org entries that are a ground-truth list of portfolio companies; no scraping guesswork needed.
- **Pages with clear repeated card patterns** that our current link-filter approach doesn't exploit. When 70 `<article class="single-card">` siblings exist in a row, that repetition is a very strong positive signal — stronger than any individual heuristic on a single anchor.

These cases are structurally different from the `_MAX_COMPANIES` / empty-alt gaps. Solving them requires reaching for more capable tools rather than tuning the current pipeline.

## What Changes

This is a **placeholder proposal** parking three candidate enhancements for future investigation. Each is a separate bet; none is committed. Before any implementation, we need:

1. A survey of 10-20 real PE/VC sites to estimate how often each pattern actually occurs in practice.
2. A cost model for the AI-heavy option (Lever 7) since HTML is more expensive than text.
3. A decision on which option (or combination) to fund first.

### Lever 5 — Repeated-card-pattern detector

Detect repetition in the DOM: N sibling elements with matching tag+class (e.g., 70 `<article class="single-card">`). Extract each card as a unit. Strong positive signal — far more robust than anchor-by-anchor heuristics.

Open questions:
- How to pick the "portfolio container" when multiple repetition patterns exist (grid + nav + cta-cards)?
- Minimum N to trigger? Cards may not all have the same class if CSS hides them.
- How does this compose with the existing link-extraction path?

### Lever 6 — JSON-LD / schema.org ItemList extraction

Parse embedded `<script type="application/ld+json">` for schema.org `Organization` or `ItemList` entries. When present, this is ground truth — no heuristic needed.

Open questions:
- What fraction of PE sites actually publish this? Anecdotal guess: < 10%. Needs measurement.
- Is a partial ItemList (e.g., only 10 of 70 companies tagged) a signal to trust or ignore?

### Lever 7 — HTML-aware AI extraction

Replace the text-only AI extraction path with one that receives filtered HTML and returns a structured company list. The LLM can reason about DOM repetition, classes, and logo filenames holistically — effectively subsuming Levers 5 + 6.

Open questions:
- Token cost: filtered HTML of a large portfolio page might be ~50-100k tokens. At ~$5/M input tokens that's $0.25-0.50 per scan. Compared to the current ~$0.02 per scan, a 10-25× cost increase — justifiable only if recall materially improves on sites where Levers 1-6 fall short.
- Latency: HTML-heavy prompts increase single-call latency. Probably fine inside the 15-min SQS budget but worth measuring.
- Does this replace the heuristic path entirely, or supplement it?

## Capabilities

### New Capabilities

_(None yet — this is a holding proposal. Capabilities will be defined if/when any individual lever is promoted to a concrete change.)_

### Modified Capabilities

_(None — same reason.)_

## Impact

- **None in this repository** until one of Lever 5/6/7 is promoted to a standalone change proposal with design + tasks.
- Companion to the tactical `raise-discovery-recall` change (Levers 1-4). If those land and recall reaches an acceptable threshold for the current customer base, Levers 5-7 may never need to ship. If specific customer sites are still failing post-1-4, this doc is the starting point for the next investigation.

## Action Items (Not Implementation)

- [ ] Survey 10-20 real PE/VC websites (manual or scripted); bucket by DOM pattern (WordPress, custom React, structured-data-rich, JS-heavy, other)
- [ ] For the "still failing" bucket, decide which lever(s) offer the highest recall-per-investment-dollar
- [ ] Promote the winning lever to its own change (`card-pattern-detector`, `jsonld-discovery`, or `html-ai-extraction`) with full design + tasks
