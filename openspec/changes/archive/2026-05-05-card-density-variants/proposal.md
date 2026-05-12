## Why

UX review **Audit 3** flagged that ~20 cards on the analysis detail page share the single `.card` CSS class but render at wildly different densities — same surface design doing too much work alone, with each caller bespoke-padding via inline styles to compensate. Concrete examples from the audit:

| Card | Density | Inline padding |
|---|---|---|
| Overall AI Risk Score | sparse (one number, one badge) | `2rem` |
| Risk Dimensions | high (16 data points in radar + axis labels) | `1.5rem` |
| Risk Breakdown card (×8) | medium (number + name + tier) | none (button reset) |
| Opportunity card (×5) | low until expanded (title, badges) | `1.25rem` |
| Value chain step (×8) | high (name + role + risk chips) | none |
| Top-3 Immediate Actions | medium (3 numbered items) | `1.25rem 1.5rem` |
| Document list row | low | `0.75rem 1rem` |
| EBITDA inner container | medium | `1rem` |

48 `.card`-class consumers across the frontend. Each makes its own decision about padding, internal typography, and how the card "should feel" — fragmenting the design system. New components reach for a custom inline padding value rather than picking from a known set, so the page accretes more variations every time.

The fix is small but high-leverage: introduce 2-3 explicit card variants (`.card--metric`, `.card--list`, `.card--rich`) with locked typography and density per variant. Then audit existing consumers and reassign. Future cards pick a variant rather than rolling their own padding.

## What Changes

- **Add** three BEM-style variant classes to `globals.css`:
  - `.card--metric` — sparse, single-number / single-badge / single-graphic cards. Generous padding, large central content. Examples: Overall AI Risk Score, single-stat cards.
  - `.card--list` — compact list rows. Tight padding, single-line baseline, often used inside expandable accordions. Examples: Opportunity cards, Risk Breakdown cards, Value Chain steps, document list rows.
  - `.card--rich` — multi-element cards. Medium padding, comfortable internal spacing for paired sub-elements. Examples: Risk Dimensions (radar + axis labels), Top-3 Immediate Actions, EBITDA wrapper, business-model summary.
- **Migrate** `analysis-detail-page` consumers to apply the appropriate variant alongside the existing `.card` class. Each migration: `className="card"` → `className="card card--metric"` (or `--list` / `--rich`), and remove the now-redundant inline `padding` style that the variant locks in.
- **Preserve** the bare `.card` class as-is — no breaking change for non-analysis-detail consumers (AnalysesTable, ScanProgressPhase, ComparisonView, etc.). They keep `.card` until a future migration. The variant classes are *additive* — they add density rules on top of the existing `.card` base.
- **Document** the picker rule: a comment block at the top of the variant section in `globals.css` lists when to use each variant, so future contributors don't reach for `.card--metric` for a list row out of habit.
- **No backend changes.** No data, API, analytics, or component-contract changes — purely CSS + className edits.

## Capabilities

### New Capabilities

<!-- None. The variants live within the analysis-detail-narrative capability surface; this is a refinement of the existing card-rendering pattern. -->

### Modified Capabilities

- `analysis-detail-narrative`: extends with one new requirement governing the variant rule on the analysis detail page — every `.card` element rendered on that page MUST apply one of the three variants, and the inline padding override pattern is forbidden for new consumers.

## Impact

**Code:**

- `frontend/src/app/globals.css` — add three new variant rules (~30-40 lines total). Comment block at top of the section documents the picker rule.
- Analysis-detail-page consumers — each migrates from `className="card" style={{ padding: '...' }}` to `className="card card--{variant}"` and the inline padding deletes. Specifically:
  - `AnalysisOverviewCards.tsx` — Overall Risk Score block becomes `card card--metric`; Risk Dimensions block becomes `card card--rich`
  - `RiskBreakdown.tsx` — each risk row becomes `card card--list`
  - `OpportunitiesList.tsx` — each opportunity card becomes `card card--list`
  - `ValueChainDiagram.tsx` — each value-chain step card becomes `card card--list`
  - `EbitdaSection.tsx` — inner card wrapper becomes `card card--rich`
  - `TopActionsCallout.tsx` — outer callout becomes `card card--rich`
  - `DocumentUpload.tsx` — document list rows become `card card--list`
  - `analysis/ReanalyzeProgressCard.tsx` — already at the right size; becomes `card card--rich`
- Updates to existing tests that asserted on inline padding values — assertions update to query the variant class on the wrapper instead.

**Out-of-scope consumers (kept as bare `.card`):**

- `AnalysesTable.tsx`, `EmptyState.tsx`, `ComparisonView.tsx`, `ComparisonScoreCards.tsx`, `ComparisonRadar.tsx`, `ComparisonRiskTable.tsx`, `ScanProgressPhase.tsx`, `PortfolioConfirmPhase.tsx`, `FailedAnalysisView.tsx`, and all other non-analysis-detail-page consumers
- These keep `.card` alone until a separate proposal migrates them. The variants don't break them; they just don't get the density rules.

**Surfaces affected:**

- Analysis detail page success path (every section that renders one or more `.card` elements)

**Data / APIs / dependencies:** none

**Out of scope (explicitly deferred):**

- Migrating non-analysis-detail-page consumers (separate proposal once the variant set is settled)
- Adding more variants beyond the initial three — additive in a future change if the three don't cover a real case
- Replacing the `.card` base class entirely — not breaking the existing API
- ExpandableCard component (item A in the UX-review queue, separate proposal — but ExpandableCard will use `.card card--list` once both ship)
- Section-spacing tokens (item C2, separate proposal — extends `--section-gap-y` to vertical rhythm)
