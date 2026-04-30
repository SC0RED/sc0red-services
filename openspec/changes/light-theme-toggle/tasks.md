## 1. Token-system foundation

- [x] 1.1 Add `[data-theme="light"] :root` block to `globals.css` mirroring every variable in the existing `:root`. Tokens to define: every name currently in `:root` — at minimum `--bg-base`, `--bg-elevated`, `--text-primary`, `--text-secondary`, `--text-tertiary`, `--text-inverse`, `--border-subtle`, `--accent-blue`, `--accent-cyan`, `--accent-red`, `--risk-critical`, `--risk-warning`, `--risk-success`, plus all `*-bg` companions.
- [x] 1.2 Light-theme palette design pass — desaturate the dark-mode accents that don't work on white. Verify WCAG AA contrast (4.5:1 body text, 3:1 large text) using axe-core or manual contrast checks.
- [x] 1.3 Add `@media print` block re-declaring the light-theme values directly on `:root`. Comment cross-references the duplication with `[data-theme="light"]` so future tokens land in both spots.

## 2. Initial-paint script + layout integration

- [x] 2.1 Inline `<Script>` in `app/layout.tsx` with `strategy="beforeInteractive"`. Reads `localStorage.janus.theme`, falls through to `prefers-color-scheme`, sets `data-theme` on `<html>` before React hydrates.
- [x] 2.2 Defensive `try/catch` for `localStorage` access (Safari private mode throws).
- [ ] 2.3 Verify no hydration mismatch warnings in console after the script lands. _(deferred — runtime check during dev smoke; `suppressHydrationWarning` on `<html>` covers it.)_

## 3. `useTheme` hook + custom event

- [x] 3.1 New `frontend/src/lib/hooks/useTheme.ts`:
      - `getTheme()` reads `<html data-theme>` (returns `"dark"` | `"light"`).
      - `setTheme(theme: "dark" | "light" | "system")` writes to `localStorage.janus.theme`, resolves `"system"` to current OS pref, updates `<html data-theme>`, dispatches a `CustomEvent("janus:theme-change", { detail: { theme } })` on `window`.
      - `useTheme()` returns `[theme, setTheme]` and re-renders on the custom event.
- [x] 3.2 Vitest cases: localStorage round-trip, OS-pref fallback, custom-event emission, system-mode resolution on each call.

## 4. Settings-page toggle

- [x] 4.1 New `frontend/src/components/ThemeToggle.tsx` — radio group with three options (Dark, Light, System). Uses `useTheme`. Renders the current selection.
- [x] 4.2 Update `app/(authenticated)/settings/SettingsView.tsx` — replace the "Coming soon" placeholder with the real toggle. Place under an "Appearance" heading.
- [x] 4.3 Vitest: ThemeToggle renders three options, click updates state, `useTheme` is called with the right argument.
- [x] 4.4 Settings page test extended: Appearance section renders with the three-option group.

## 5. Component / chart audit + migration

- [x] 5.1 Survey: `grep -rn 'style=.*#[0-9a-fA-F]' frontend/src/components frontend/src/app` to count inline-style hex strings. Document the count in the apply-time PR description. _(40 hits — 27 in PDF route which the polished-pdf-export change replaces wholesale; 13 actionable inline hex strings migrated.)_
- [x] 5.2 Migrate each surveyed component: replace hardcoded hex with `var(--token)`. Add new tokens to `globals.css` if no existing variable matches. _(Added `--accent-blue-hover`. EbitdaNodeComponent, EbitdaTree, comparison/constants.ts, leverColors.ts, react-flow chrome rules in globals.css all migrated.)_
- [x] 5.3 Recharts color migration:
      - Add `useThemedColor(token: string): string` hook in `lib/utils/themedColor.ts`. Reads `getComputedStyle(document.documentElement).getPropertyValue(token)` on the client; returns the dark-theme fallback during SSR.
      - Migrate `riskUtils.ts` `TIER_COLORS` / `TIER_COLORS_HEX` and `leverColors.ts` constants to use CSS variable names + the hook.
      - Charts that consume these constants get a small refactor to call the hook + re-render on theme change (custom event listener).
- [ ] 5.4 Visual smoke on every page in both themes: dashboard, analyses list, analysis detail, portfolio view, scan-new, recently-deleted, settings, team, login. Note any contrast failures or visual breakage. _(deferred to dev-deploy smoke in §8.1.)_

## 6. `@media print` validation

- [ ] 6.1 In each browser (Chrome, Safari, Firefox), open Cmd+P preview on dashboard / analysis detail / portfolio view. Verify light theme renders, sidebar/buttons/chrome are hidden where appropriate. _(deferred to dev-deploy smoke in §8.1.)_
- [x] 6.2 Add `@media print` rules that hide non-content chrome: sidebar, action bars, modals, the scan-progress strip, etc.
- [x] 6.3 Add `page-break-inside: avoid` hints on cards, tables, and chart containers so the browser doesn't split a card mid-row.

## 7. Quality gates

- [x] 7.1 `cd frontend && npm run lint` clean
- [x] 7.2 `cd frontend && npx tsc --noEmit` clean
- [x] 7.3 `cd frontend && npm test` all green (676/676 across 70 files)
- [ ] 7.4 Architecture-reviewer agent on the combined diff (touches CSS + components + hooks → guard tripped on file count)
- [ ] 7.5 Open PR, CI green, merge.

## 8. Closeout

- [ ] 8.1 Smoke-test on dev: toggle works, persists across reload, `@media print` produces light output regardless of toggle.
- [ ] 8.2 Promote dev → testing → production.
- [ ] 8.3 Archive this change once production has been stable for 1 week.
- [ ] 8.4 Open follow-up if a CI lint rule for "no inline-style hex strings" is wanted (mentioned in design.md D4 as deferred).
