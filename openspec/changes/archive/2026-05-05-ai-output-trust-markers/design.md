## Context

**Confidence today** — `ConfidenceMarker = 'HIGH' | 'MEDIUM' | 'LOW'` is a backend-emitted field on every strategy-map objective (Financial × N, Customer × N, InternalProcess × N, Capacity × 3 = ~12-20 objectives per analysis). It currently renders in two places per objective:

1. **Header chip** in the tooltip — via `<ConfidenceChip>` (line 289 of `StrategyMapNode.tsx`), as a colored pill with `--risk-low-bg` / `--risk-low` for HIGH, `--risk-moderate-bg` for MEDIUM, neutral grays for LOW.
2. **8-pixel dot** on the chip header next to the objective ID (line 157 of `StrategyMapNode.tsx`) — uses `CONFIDENCE_DOT` map with the same risk-tier palette.

Both visual treatments share the green/amber/red palette with the page's risk-tier system. UX Audit 5 calls this out specifically: a green chip on a strategy-map objective reads as "low risk" when it actually means "high confidence."

**Provenance today** — the `synthesised: boolean` field appears on three types: `VisionStatement`, `MissionStatement`, `CoreValues`. It renders as bare parenthetical text:

```tsx
// StrategyMapHeader.tsx — Vision
{vision.synthesised ? (
    <span style={{ marginLeft: '8px', fontStyle: 'normal', fontSize: '0.7rem',
                   color: 'var(--text-tertiary)', fontWeight: 600,
                   letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        (synthesised)
    </span>
) : null}

// StrategyMapHeader.tsx — Mission
label={`Mission${mission.synthesised ? ' (synthesised)' : ''}`}

// StrategyMapView.tsx — CoreValues
{values.synthesised ? ' (inferred)' : ''}

// PrintStrategyMap.tsx — three identical inline patterns
```

Three different inline-style implementations of the same uppercase-tracking-tertiary visual. None is a styled component.

**The trust signal grouped together.** Confidence and provenance both answer "should I trust what the AI says here?" Solving them as one design move yields a coherent vocabulary: green/amber/red for risk, neutral dots for AI confidence, neutral pill for AI provenance. Three signals, three visual encodings, no overlap.

## Goals / Non-Goals

**Goals:**

- A single ConfidenceIndicator component, used everywhere a `ConfidenceMarker` value is rendered today. Visual: 3-dot scale (`●●● / ●●○ / ●○○`) in a single neutral color. Accessible name conveys the level ("Confidence: high"). Tooltip preserves the existing long-form rationale.
- A single ProvenanceMarker component, used everywhere `synthesised: boolean` is rendered today. Visual: small icon + label, e.g. `🤖 inferred` (icon TBD; design D3). Accessible name conveys the meaning ("AI-inferred from absence" or similar).
- Risk-tier palette (`--risk-low/moderate/high/critical`) is no longer used for confidence rendering — closes the Audit-5 collision.
- Inline-styled `(synthesised)` parentheticals consolidate to a single component — closes the Audit-7 inconsistency.
- Print path uses the same components (no separate print-only treatment).
- No backend changes. No data, API, or analytics changes. No changes to where `ConfidenceMarker` or `synthesised` fields are emitted.

**Non-Goals:**

- Adding `synthesised` or `confidence` to data types that don't have them today (Opportunity, EbitdaNode, ValueChainStep). Tracked in the proposal's out-of-scope list — own proposal.
- Differentiating provenance kinds beyond `inferred` for v1 (component is forward-compatible but only one kind ships).
- Risk-tier palette redesign beyond removing it from confidence usage.
- Replacing or rebuilding `ConfidenceChip` consumers (e.g., `PrintStrategyMapObjectives`) with a different abstraction — ConfidenceIndicator IS the replacement.
- ExpandableCard, card-density-variants, section-spacing-tokens — separately queued.

## Decisions

### D1 — ConfidenceIndicator visual: 3-dot scale, single neutral color

User pre-decided "dot scale" in the explore-mode discussion. Implementing as:

```
HIGH    →  ●●●     (3 filled dots)
MEDIUM  →  ●●○     (2 filled, 1 hollow)
LOW     →  ●○○     (1 filled, 2 hollow)
```

Single neutral color: `var(--text-secondary)` for filled, `var(--border)` for hollow. No risk-tier palette involvement.

Three rejected alternatives:

| Option | Why rejected |
|---|---|
| **Different colors per level** (e.g., dark/medium/light gray) | Reintroduces a palette gradient that competes with risk-tier in peripheral vision. Single-color preserves "different concept, different visual" |
| **Text-only** (`Confidence: high` without color) | Verbose; eats horizontal space inside tight tooltip headers and wide-but-short table cells |
| **Filled circle scale** (`◐ ◑ ●`) | Cute but ambiguous direction — does crescent mean "halfway full" or "halfway empty"? Filled-vs-hollow dot scale is unambiguous |

**Why 3 dots and not 5 (more granular)?** Backend emits 3 levels; rendering 5 would imply granularity that doesn't exist.

### D2 — Consolidate the 8-px header dot into the indicator OR keep both

`StrategyMapNode.tsx` line 157 currently renders an 8-px circular confidence dot in the chip's HEADER row (alongside the objective ID), AND `ConfidenceChip` renders a separate larger pill in the TOOLTIP body (line 289). Both encode the same data point.

Two options:

| Option | Pros | Cons |
|---|---|---|
| **A. Keep both** — small dot on header (compact preview), full indicator in tooltip (full detail) | Header reader sees confidence at a glance without opening the tooltip | The header dot uses the risk-tier palette today; if I migrate it to the new neutral palette, the chip's already-busy header row gets a third subtle visual. If I keep it on the risk palette, Audit-5 collision persists |
| **B. Remove the header dot** — confidence only renders in the tooltip via the new indicator | Cleaner header row; one canonical confidence rendering | Confidence is no longer visible without hovering / focusing the chip |

**Pick: A, but migrate the header dot to neutral palette.** Rationale: the header dot is a useful at-a-glance signal for power users scanning many chips; removing it loses information. Migrating it to a neutral 3-dot mini-scale (`●●●` rendered tiny) is consistent with the indicator and closes the collision. The tooltip still shows the full indicator with tooltip-on-hover for the long-form rationale.

Implementation: ConfidenceIndicator component takes a `size?: 'small' | 'default'` prop. Header uses `size="small"` (no tooltip-on-hover; just the visual). Tooltip body uses `size="default"` (with the `title` attribute for the rationale).

### D3 — ProvenanceMarker visual: icon + label

Visual: small inline element with a sparkle/AI icon + label.

```
✦ Inferred       (small accent-blue icon + uppercase tertiary text)
```

Specific styling matching the existing parentheticals' uppercase-tracking-tertiary baseline:

```css
.provenance-marker {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-tertiary);
}
.provenance-marker-icon {
    /* small SVG, currentColor fill */
    width: 10px;
    height: 10px;
    color: var(--accent-blue);
}
```

Accessible name: `<span className="provenance-marker" aria-label="AI-inferred">✦ Inferred</span>` — the icon is `aria-hidden`, the visible label provides the readable text, and the wrapper's aria-label clarifies the meaning.

Three rejected alternatives:

| Option | Why rejected |
|---|---|
| **Emoji icon (🤖)** | Cross-platform inconsistent rendering; emoji width varies; not stylable |
| **Text-only** (`Inferred`) | Loses the visual distinguishability — readers scanning peripherally would not see the marker as a distinct element vs the surrounding text |
| **Outlined badge with border** | Heavy — competes for visual attention with the heading or label it accompanies. The marker should be subtle, not loud |

**Why a sparkle/star icon (`✦`)?** Common UX shorthand for "AI did this" (used by Anthropic, OpenAI, Google product UIs). Cleaner than a brain or robot icon. Will use an inline SVG, not the Unicode glyph (cross-platform consistency).

### D4 — Component file location

Both new components live at `frontend/src/components/analysis/`. Rationale:

- `ConfidenceIndicator` and `ProvenanceMarker` are page-level trust signals applied across the analysis detail page (and its print path). They're not strategy-map-specific.
- `ConfidenceChip` lived at `frontend/src/components/strategy-map/` because it was strategy-map-only. The new indicator's broader applicability (future: opportunities, EBITDA, etc.) deserves the page-level home.
- Import path: `@/components/analysis/ConfidenceIndicator`, `@/components/analysis/ProvenanceMarker`. Clean.

### D5 — `ConfidenceChip` deletion

After all consumers migrate, `ConfidenceChip.tsx` is deleted. The component has exactly two consumers today: `StrategyMapNode.tsx` (production) and `index.ts` (barrel export). Both update; the file goes away. Removes a stale component before it accretes more callers in patterns we want to phase out.

If `ConfidenceChip` had broad consumer footprint, this would be risky — but with only one production consumer, the migration is safe and the deletion is the right cleanup.

### D6 — Test coverage strategy

Two new test files:

1. **`ConfidenceIndicator.test.tsx`** — renders correct dot count for each level (HIGH=3, MEDIUM=2, LOW=1); accessible name matches the level; default vs small size variants render with appropriate sizes; no risk-tier-palette CSS variable appears in computed styles (regression guard for the Audit-5 collision).

2. **`ProvenanceMarker.test.tsx`** — renders the label + icon for `kind="inferred"`; accessible name conveys the AI-inferred meaning; icon is `aria-hidden`.

Updates to existing tests:

- `StrategyMapNode.test.tsx` — assertions that previously queried `ConfidenceChip` text ("HIGH", "MEDIUM", "LOW") update to query the new accessible name (`getByLabelText('Confidence: high')`).
- `StrategyMapHeader.test.tsx` (if exists) — update inline `(synthesised)` text assertions to query the new ProvenanceMarker.

### D7 — Print path treatment

`PrintStrategyMap.tsx` currently renders three inline `(synthesised)` parentheticals. The new `ProvenanceMarker` works in print (no browser-only APIs, no animations). It just renders cleanly with the print stylesheet. Single component for screen + print is the right move.

ConfidenceIndicator is NOT used in `PrintStrategyMapObjectives.tsx` today — the print path may render confidence differently (text + numeric, not dots). Verify during implementation; if the print path uses ConfidenceChip directly, migrate it; otherwise leave the print confidence treatment alone (separate proposal).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Removing the colored pill might reduce the visual prominence of confidence on the strategy map | Header dot stays (D2), so power users still see confidence at a glance. Tooltip body indicator is more prominent (3 dots > 1 dot). Net visibility roughly unchanged |
| Dot scale at small sizes (8-10 px) may be hard to distinguish | CSS specifies sufficient size (3 dots × 6 px each + 2 px gaps = 22 px wide minimum, fine on desktop and mobile). Test in actual UI before merge |
| `ConfidenceChip` deletion breaks any consumer I missed in grep | Grep across `frontend/src/` for `ConfidenceChip` before deletion; remove only after all references migrate. Lint catches missed imports |
| Future `confidence` field added to other types (opportunities, EBITDA) will want to consume `ConfidenceIndicator` | The component lives at `components/analysis/`, broadly applicable. Forward-compatible by design |
| ProvenanceMarker's `kind: 'inferred'` is the only kind today; future kinds may want different visual treatments | Component takes `kind` discriminator; visual variants live behind that prop. Adding `'extracted'` or `'from-upload'` later is additive, not breaking |
| The print path's `PrintStrategyMapObjectives` uses ConfidenceChip indirectly — risk of breakage | Verify during implementation. If print uses ConfidenceChip, migrate same way as screen |
| `PERSPECTIVE_ACCENT` in `StrategyMapNode.tsx` lines 48-53 maps `customer` to `var(--risk-low)` and `internal` to `var(--risk-moderate)` — i.e. left-border accents on chips still use the risk-tier palette adjacent to the new neutral confidence dots. The specific Audit-5 collision (confidence dot reads as risk tier) is solved, but the broader palette tension between perspective-accent and confidence is not | **Knowingly deferred** to a separate proposal (`decouple-perspective-accent-from-risk-palette` or similar). The perspective-accent convention is pre-existing and broader than the confidence concern; resolving it requires a design choice on what palette perspectives SHOULD use (per-perspective brand colors? Numbered themes?). Out of scope here. Architecture-reviewer pass on this change flagged the documentation gap; this row closes it |

## Migration Plan

Frontend-only, presentation-only.

1. PR merges to `development`
2. Amplify auto-deploys
3. Manual visual verification: load an analysis with a strategy map; confirm dots render at the right counts; confirm provenance markers replace the parentheticals on Vision/Mission/CoreValues; print preview confirms the print path also renders correctly

**Rollback:** `git revert` of the merge commit. No data implications.

## Resolved Questions

- **Confidence visual: dot scale vs other** → **Dot scale** per user choice in explore mode. Single neutral color, 3-dot filled-vs-hollow.
- **Provenance scope: just `synthesised: true` or also opportunities/EBITDA/ValueChain?** → **Just current data.** Backend extension is its own proposal — explicit out-of-scope here.
- **Header dot on strategy-map chips: keep or remove?** → **Keep, migrate to neutral palette.** D2 rationale.
- **`ConfidenceChip` after migration: delete or keep?** → **Delete.** D5.
- **Print path: same components or separate?** → **Same components.** D7.

## Open Questions

1. **What sparkle/star SVG icon to use for ProvenanceMarker?** Defer to implementation — pick an existing icon convention in the codebase (lucide-react if used; otherwise a hand-rolled inline SVG matching existing inline-icon style in `AnalysisHeader`).
2. **Should the dot scale be horizontal (`●●○`) or vertical (one column of 3 dots)?** Defer to implementation — horizontal is the convention; revisit if vertical reads better in the strategy-map chip header where horizontal space is tight.
