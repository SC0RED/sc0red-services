## Why

Tier 1 (`webapp-ux-foundations-tier1`) covers the day-one UX foundations — Toast, Cmd-K, Settings, scan provenance. This proposal — Tier 2 — covers the patterns that bite at scale: pagination, server-side search, URL-as-state, help tooltips, bulk actions, relative timestamps, and the org activity feed.

These are not visible until the app is being used in earnest. With 30 analyses the current `/analyses` page is fine; with 200 it slows; with 1,000 it's broken. With one user nobody needs an activity feed; with five teammates running scans in parallel, "what changed since I last looked?" becomes a daily question.

This is the second of two umbrella proposals. Tier 1 should ship before Tier 2 — toast in particular is a dependency for several Tier 2 items (e.g., bulk actions confirm via toast, copy-link affordances use toast). Tier 3 polish (light mode, mobile breakpoints, audit log surfacing) is captured separately if/when it's prioritized.

## What Changes

1. **Pagination + server-side search on /analyses** — backend already supports `?limit=N&cursor=JSON`; the frontend ignores it. Today's page fetches every analysis the org owns and filters/sorts client-side. We adopt **option B from the exploration**: search runs server-side (`?q=foo` query param), filter and sort stay client-side over the loaded slice. Cursor pagination via "Load More" or numbered pages.

2. **URL-as-state for filters** — `/analyses?q=acme&tier=high&type=portfolio&sort=score-desc` should be shareable. Today filter state is `useState`-only; refresh resets, sharing the URL doesn't reproduce the view. Adopt URL search params as the source of truth.

3. **Help / domain tooltips for PE jargon** — "Risk Tier", "EBITDA Tree", "Value Lever", "Active Lever Filter" all need a one-sentence inline explainer (small `ⓘ` icon, hover/click reveals). Especially important for new users on the team.

4. **Bulk actions on analyses list** — checkbox column, floating "Delete N selected" toolbar. Reduces friction for housekeeping (deleting stale scans, batch-tagging if/when tags exist).

5. **Relative timestamps everywhere** — replace raw `2026-03-12T10:00:00Z` strings with "3 hours ago" + tooltip showing the absolute time. One utility, used across analyses table, scans, dashboard recent items, analysis detail.

6. **Org activity feed / persistent inbox** — when Bob runs a scan, Alice should see it in an Activity panel. Different from Toast (ephemeral feedback for the actor); this is for "what's happening across my org." Can start as a sidebar panel showing the last 20 events; full inbox UX is a future polish.

**Explicitly out of scope** (so reviewers don't conflate):

- Anything from Tier 1 (Toast, Cmd-K, Settings, scan provenance) — see `webapp-ux-foundations-tier1`
- Light mode toggle, mobile breakpoints, audit log surfacing — Tier 3 polish, not yet captured
- Real-time push for activity feed (websockets / SSE) — start with poll-based; push is a future optimization
- Notification email — separate channel, separate design; this proposal scopes to in-app activity surface

## Capabilities

### New Capabilities
- `domain-tooltips`: ⓘ-driven inline explainers for PE-domain terms (Risk Tier, EBITDA Tree, Value Lever, etc.) — single shared `<HelpTooltip>` component + a content registry.
- `bulk-actions`: row-selection + floating action bar pattern, applied first to the analyses list (delete bulk).
- `relative-time`: a single `<RelativeTime>` component (and util) used everywhere a timestamp appears — outputs "3 hours ago" with absolute-time tooltip.
- `activity-feed`: org-level event surface in the sidebar / dedicated panel. Backend exposes `GET /activity` returning recent events; frontend renders chronologically.

### Modified Capabilities
- `analyses-listing`: pagination + URL-as-state + server-side search. **Note**: this capability doesn't exist as a spec file today; this proposal will create it as the spec for the analyses-list page (instead of putting requirements in `authenticated-layout` where they don't quite fit).

## Impact

**Backend code**:
- Extend `GET /api/analyses` to accept a `q` query param for server-side fuzzy search over `company_name`, `industry`. The existing `?limit=N&cursor=JSON` is already wired.
- New `GET /api/activity?limit=N&cursor=...` endpoint that emits recent org-level events. Source: scan creation, scan completion, scan deletion, analysis completion, analysis deletion, member invite, member join. Likely projects from existing DynamoDB records (audit-log-on-read pattern) for v1; may add an explicit events table later.

**Frontend code**:
- Refactor `/analyses` to read filter state from URL (Next.js `useSearchParams`); refactor `AnalysesTable` to consume server search results + cursor.
- New components: `<HelpTooltip>`, `<BulkActionsBar>`, `<RelativeTime>`, `<ActivityPanel>`.
- New util: `lib/utils/relativeTime.ts` (could use `date-fns/formatDistanceToNow`; check whether already in deps).
- Sidebar update: optional Activity panel slot or new `/activity` route.

**API contract**:
- Additive: `?q=` on `/api/analyses`, new `/api/activity` route. Existing clients keep working.

**Tests**:
- New vitest tests for each component.
- New backend pytest cases for `?q=` search, activity event projection, cursor pagination edge cases (empty cursor, invalid cursor, last page).
- E2E should add at least one case for "search persists across reloads" (URL-as-state).

**Quality gates**: ruff, pyright, pytest (≥ 95% coverage), npm lint, tsc, vitest, architecture-reviewer agent, E2E.

**Migration / risk**: zero data migration. New endpoints are additive. The URL-as-state migration on `/analyses` is the riskiest item — bookmarks and shared URLs from the pre-state world keep working (no params = no filter, same as today).
