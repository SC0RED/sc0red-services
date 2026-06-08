# Help-content registry — copy reference

The `<HelpTooltip term="..." />` component pulls its title + body from the
TypeScript registry at `frontend/src/lib/help-content.ts`. This file is a
plain-markdown mirror of that registry so non-engineers can review and edit
the copy without touching code.

## How to edit

1. **Edit the explainer here first** if you only care about the wording.
   The phrasing should remain 1-2 sentences of plain text — the popover is
   a quick orientation, not a glossary entry.
2. **Hand the diff to engineering** to update the matching key in
   `frontend/src/lib/help-content.ts`. The two files must stay in sync —
   the audit script `scripts/check-help-content.mjs` (run on every CI build
   via the `check:help-content` package script) fails the build otherwise.

## Registry

> **Source of truth**: `frontend/src/lib/help-content.ts`. This document
> mirrors that file for human review. If they drift, CI will fail.

### `risk_tier` — Risk Tier

A coarse bucket — Low, Moderate, High, or Critical — derived from the overall risk score. Tiers exist so analysts can scan a portfolio at a glance without reading every score.

### `risk_score` — Risk Score

A 0-10 composite score across multiple risk categories (regulatory, operational, financial, etc). Higher means more risk. The breakdown by category is visible on the analysis detail page.

### `ebitda_tree` — EBITDA Tree

A breakdown of the company's earnings drivers — revenue lines minus cost lines, organised so each leaf is an addressable lever. The tree highlights where opportunity and risk concentrate.

### `value_lever` — Value Lever

A specific way to grow the business — either by lifting revenue (Revenue Side) or reducing cost (Cost Side). Each opportunity card is tagged with the lever it pulls.

### `active_lever_filter` — Active Lever Filter

Filter the opportunities list to only show levers on one side of the EBITDA tree. Use this to focus on revenue plays separately from cost plays.

### `industry` — Industry

The company's primary industry, classified during the initial scan. Used for benchmarking against peers in the same sector.

### `impact_rating` — Impact Rating

A qualitative estimate (Low / Medium / High) of how much an opportunity could move the company's value if executed. Combined with effort to prioritise the playbook.

### `scan` — Scan

A scan is the job that crawls one source — a single company (Standalone) or a PE firm's portfolio page (Portfolio) — and produces a risk analysis for each company it finds. Its status shows crawl progress until complete.

### `analysis` — Analysis

An analysis is the finished risk report for one company, produced by a scan. Recent Analyses lists the per-company results; open one for its full risk-score breakdown.

### `scan_type` — Standalone vs. Portfolio

Standalone scans assess a single company; Portfolio scans crawl a PE firm's holdings and produce one analysis per portfolio company. The Source/Type badge shows which kind produced a row.
