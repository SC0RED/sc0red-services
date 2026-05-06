## Why

Janus ships dark-theme-only today. `globals.css` is 1620 lines of single-`:root` CSS with no light-mode tokens, no `[data-theme]` switcher, and no `prefers-color-scheme` handling. Two real consequences:

1. **Print-from-the-app produces unusable output.** Browser print dialogs either dump a black background (toner-heavy, low-contrast) or — with `print-color-adjust: economy` — wash everything to grey. Neither is presentable.
2. **Light-mode preference goes unmet.** Users who work long sessions, or print a lot, or simply prefer light backgrounds have no toggle.

This proposal adds a proper light theme: a dual palette via `[data-theme="light"]` overriding the existing `:root` variables, a Settings-page toggle persisted to `localStorage`, and `@media print` that forces the light theme regardless of user choice. Every component continues using the existing CSS variable names — the migration is "audit hardcoded hex strings, replace with `var(--token)`"; the variable values change between themes, the names don't.

This change is also a dependency for the upcoming `polished-pdf-export` change. The PDF render uses an auth-gated `/print/{analysisId}` route that inherits the light theme automatically — without this, the PDF route would carry duplicate inline light-mode CSS that would drift from the live app.

## What Changes

- **`globals.css` token strategy**: every dark-theme value in `:root` gets a counterpart under `[data-theme="light"] :root`, scoped via the same variable names (`--bg-base`, `--text-primary`, `--accent-blue`, etc.). Existing components consuming `var(--bg-base)` get the right value automatically; no per-component refactor for components that already use tokens.
- **Component / chart audit**: components using inline-style hardcoded hex strings (e.g., `style={{ background: '#060A12' }}`) migrate to `var(--token)`. Recharts colors in `lib/utils/riskUtils.ts` and `lib/utils/leverColors.ts` move from hardcoded hex constants to a `useThemedColor()` hook (or a CSS-variable-resolving helper) so chart hues track the active theme.
- **Settings page toggle**: a "Appearance" section in `/settings` (matches the placeholder from Tier 1 §4). Three options — `Dark`, `Light`, `System (follow OS)`. Selection persists to `localStorage` under key `janus.theme`.
- **Initial theme on cold load**: a tiny inline script in `app/layout.tsx` reads `localStorage.janus.theme` (or falls back to `prefers-color-scheme`) and sets `data-theme` on `<html>` BEFORE React hydrates, eliminating the flash-of-wrong-theme on first paint.
- **`@media print` override**: `globals.css` adds a `@media print { :root { /* re-declare light values */ } }` block so any `Cmd+P` from the live app renders light-on-white regardless of the user's screen preference.
- **Reduced motion / accessibility**: contrast checked in both palettes against WCAG 2.1 AA (4.5:1 for body text, 3:1 for large text). Critical because dark-theme saturated hues (e.g., `--accent-blue: #3B7BF6` on `--bg-base: #060a12`) don't necessarily survive translation to a light palette.

## Capabilities

### New Capabilities

- **`light-theme-toggle`** — admin/user-controlled theme preference with three modes (dark / light / follow OS), persisted client-side, with `@media print` override.

### Modified Capabilities

_None_ — every existing surface keeps working unchanged. The migration is internal (CSS tokens, inline-style cleanup); no contract surfaces change.

## Impact

**Modified**:
- `frontend/src/app/globals.css` — adds `[data-theme="light"] :root` block (~70 lines of token declarations) and a `@media print` block (~30 lines)
- `frontend/src/app/layout.tsx` — adds the inline theme-init script
- `frontend/src/lib/utils/riskUtils.ts` and `lib/utils/leverColors.ts` — chart-color tokens become CSS-variable-driven
- Components with inline-style hex strings — audited and migrated. Estimated 15–30 component files; concrete count from a `grep` survey at apply time.
- `frontend/src/app/(authenticated)/settings/SettingsView.tsx` — new "Appearance" section with the three-option toggle

**Added**:
- `frontend/src/lib/hooks/useTheme.ts` — read/write the active theme; emits a custom event when it changes so chart hooks can re-resolve their colors
- `frontend/src/components/ThemeToggle.tsx` — the actual radio-button group used in Settings

**Tests**:
- `useTheme` unit tests (localStorage round-trip, OS-pref fallback, custom-event emission)
- `ThemeToggle` component tests (renders three options, click updates state)
- Settings page test extended (Appearance section renders, toggle persists)
- Visual-regression smoke (manual on dev): every page in dark and light, print preview check

**Operational**: zero — purely client-side. No infra change, no data migration, no Lambda edit.

**Migration / risk**:
- The audit step is the largest unknown. If many components use inline-style hardcoded hexes, the diff is sprawling.
- Recharts is the trickiest part. Charts render server-side in Next.js (in some surfaces); the chart-color hook needs to work both in SSR and on the client.
- Initial theme flash-of-wrong-color is mitigated by the inline script in `<head>`. Standard pattern — well-trodden in modern React apps.

## What We're NOT Doing

- **System-wide dark/light auto-switch on time-of-day** — out of scope. User chooses, OS pref is the default; no time-based heuristics.
- **Per-page theme override** — every authenticated surface uses one global theme. The PDF route (and `/print/{id}` once `polished-pdf-export` lands) hard-locks to light regardless of user choice.
- **Custom themes / brand color overrides** — not a multi-tenant concern at this scale. One dark, one light.
- **High-contrast / accessibility palette** — separate scope. WCAG AA contrast is the target; AAA + custom-contrast modes are deferred.
- **Mobile-specific theme behavior** — out of scope. The Tier 3 "mobile responsive" item already exists separately.

## Open Questions (resolve at apply time)

1. **Default for new users**: follow OS `prefers-color-scheme` (lean) or fixed-dark? OS-following matches modern conventions and gives users on light-mode systems a friendlier first session. Fixed-dark preserves "Janus is a dark-mode app" branding signal.
2. **Settings sidebar entry vs. placeholder**: Tier 1 §4 explicitly has a "Coming soon — light mode toggle" placeholder. Replacing it cleanly is the natural fit. Decision: replace the placeholder with the real toggle.
3. **Recharts color migration approach**: option A — chart colors become CSS variables read via `getComputedStyle`. Option B — a `useThemedColor(token)` hook. Option B is cleaner for SSR but requires every chart to import + use the hook. Decide during the component audit.
4. **Reduce-motion preference for theme transition**: add a 200ms cross-fade between themes? Cute but adds complexity. Default: instant swap, no transition.
