## Why

The Janus webapp surface (Dashboard, New Scan, Analyses, Team, Portfolio detail, Analysis detail) has a solid design system and a UI primitive library, but several SaaS-table-stakes UX patterns are missing. They aren't bugs — the app works — but they show up as small daily friction that compounds over time, especially for the power-user audience (PE analysts moving through 100s of analyses).

We explored the gaps and ranked them. Tier 1 is the "you'd notice immediately" tier — the ones a new user would hit on day one. Tier 2 (separate proposal: `webapp-ux-foundations-tier2`) covers patterns that bite at scale (pagination, server-side search, URL-as-state, etc.). Tier 3 polish (light mode, mobile breakpoints, audit log surfacing) is captured separately.

This is the Tier 1 umbrella. Five items, each independently shippable, bundled here so the foundation lands cohesively and we don't half-ship one item without the others.

## What Changes

1. **Toast / notification feedback system** — every mutation today is "page reloads and the row is gone." A global toast component + `useToast()` hook gives us "Deleted", "Invitation sent", "Re-analysis queued" feedback. Destructive actions get an "Undo" toast (5-second window) so users can move fast with safety.

2. **Cmd-K command palette + global keyboard shortcuts** — Cmd-K opens a palette over companies / portfolios / top-level actions. Bundle with `?` to show all shortcuts, `Esc` to close any modal, `/` to focus search, `g d` / `g a` / `g s` for navigation. Standard GitHub/Linear conventions.

3. **Settings / profile page** — new `/settings` route + sidebar entry. Profile section (name + email read-only via Cognito), Org info (org_id with copy button, role), and a placeholder for the Tier 3 light-mode toggle. Logout consolidated here or in the sidebar bottom — TBD during implementation.

4. **Portfolio link from analyses list + scan provenance on analysis detail** — the existing "Portfolio" / "Standalone" badge on `/analyses` rows becomes a `<Link>` to `/portfolio/{scanId}` for portfolio-type rows. On `/analysis/{id}`, a "Part of: {scan_name}" cross-reference renders near the company name. Data is already on the API response; this is purely UI wiring.

5. **Wire mutations to the toast system** — delete analysis, delete scan, invite member, re-analyze. Each triggers an appropriate toast (success / error / loading transition). Delete actions get the optional Undo affordance.

**Explicitly out of scope** (so reviewers don't conflate with adjacent work):

- Pagination on /analyses, server-side search, URL-as-state on filters → **Tier 2**
- Help / domain tooltips, bulk actions, relative timestamps → **Tier 2**
- Persistent notifications inbox (different scope from ephemeral toasts) → **Tier 2**
- Light mode toggle, mobile breakpoints, audit log surfacing → **Tier 3** (not yet captured)

## Capabilities

### New Capabilities
- `toast-notifications`: ephemeral feedback for mutations across the app — variants (success/error/info/loading), positioning, accessibility, and the Undo affordance.
- `command-palette`: Cmd-K-triggered fuzzy-search palette over companies, portfolios, and top-level actions.
- `keyboard-shortcuts`: global shortcut handler for navigation, modal-close, search-focus, and the `?` help dialog.
- `user-settings`: the `/settings` route, its sections (profile, org info, future preferences), and the sidebar entry that links to it.
- `analysis-navigation`: cross-reference UX between analyses, scans, and portfolios — including the analyses-list portfolio badge link and the analysis-detail provenance line.

### Modified Capabilities
- `authenticated-layout`: extends the sidebar nav set to include `/settings`. Existing requirements about layout persistence and route preservation are preserved.

## Impact

**Frontend code**:
- New components: `Toast`, `ToastProvider`, `useToast`, `CommandPalette`, `KeyboardShortcutsModal`, `SettingsPage` (and section sub-components).
- Modified: `DashboardSidebar` (new "Settings" entry), `AnalysisRow` (badge → link for portfolio rows), `AnalysisDetail` (scan provenance line), `DeleteAnalysisButton` / `DeleteScanButton` / invitation flows / re-analyze flow (toast wiring).
- New library dependency: `cmdk` for the command palette (~3 KB gzipped, well-maintained, used by Vercel's own dashboard) — see design D2.
- New CSS: toast animations (single shared keyframe per variant), respects `prefers-reduced-motion`.

**Backend code**: none. All five items are frontend-only — every API contract used (analyses list, analysis detail, scan list) already exposes the data needed.

**API contract**: no changes. The portfolio link uses `scanId` + `scanType` already on `AnalysisItem` and `ScanAnalysis`.

**Tests**: new vitest tests for each component (toast, palette, shortcuts modal, settings sections), plus link-href assertions for the analyses-list and analysis-detail provenance (avoid the failure-mode that #182's failed-card regression had — assert on rendered `<a href>`, not just text).

**Quality gates**: lint, tsc, vitest (~95% coverage); architecture-reviewer agent; existing E2E suite must continue to pass.

**Migration / risk**: zero data migration. All changes are additive UI. Rollback is `git revert` of the merge commits — no schema or API changes to undo.
