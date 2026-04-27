## Context

Tier 1 covers the day-one feel of the app. Tier 2 covers the day-100 feel — the patterns that quietly degrade as the app gets used at scale. With ~10 analyses today the gaps are invisible; with 100+ they're felt; with 1,000 the app breaks (the analyses page would download all 1,000 records and filter them in browser memory).

This proposal bundles six items. They're more independent than Tier 1's bundle — pagination doesn't share infrastructure with relative timestamps. The bundle exists for project-management reasons (one umbrella to track Tier 2 work) more than for technical-cohesion reasons.

```
DEPENDENCIES (within this change)

  Pagination + URL-state ──── server-side search (one PR, three problems)
                              │
                              └─> applied first to /analyses
  
  Domain tooltips      ──── independent, ships any time
  Bulk actions         ──── depends on Toast (Tier 1) for action confirmation
  Relative timestamps  ──── independent, single util touched many places
  Activity feed        ──── new endpoint + new panel; can ship last
```

The natural order: Pagination/URL/search first (one big refactor, sets the pattern for future list pages); then any of the others in any order; activity feed last (it's the most novel and would benefit from learning from the rest).

## Goals / Non-Goals

**Goals:**
- A single team running 100+ analyses sees no perceptible degradation when navigating the analyses page.
- A user can share a URL with their colleague and have them see the same filtered view.
- A new analyst can hover a domain term and learn what it means without leaving the page.
- A user can delete 10 stale analyses in one action.
- "When did this happen" is answerable at a glance for every timestamp in the app.
- Org-collab signals (someone else ran a scan) are visible without an email.

**Non-Goals:**
- Real-time push for the activity feed. Polling at 30s intervals is fine for v1; SSE/websockets is a follow-up if usage justifies it.
- Notification email infrastructure. Separate channel, separate design.
- Search across other surfaces (companies, scans, opportunities). Tier 2 scopes search to the analyses list. Cmd-K (Tier 1) covers cross-surface jumping for now.
- An "Activity" tab as a primary destination — start with a sidebar panel; promote to a route only if usage warrants.

## Decisions

### D1. Server-side search, client-side filter+sort (Option B from exploration)

**Decision:** `GET /api/analyses?q=foo&limit=N&cursor=JSON` runs server-side fuzzy search over `company_name` and `industry`. The frontend's `tier` and `type` filters and sort order stay client-side over whatever's loaded. Pagination via "Load More" cursor pattern (or numbered pages — decide during impl).

**Why not "fully client-side":** Breaks at ~500 rows. The existing /analyses page already loads everything; we're a few months from feeling the slowdown.

**Why not "fully server-side":** Server-side filter and sort means more query params, more state in the URL, and more backend complexity. Filter and sort over the currently-loaded slice is fast and fine — server-side is overkill for tier=high when the user has 50 high-tier rows out of 200 loaded.

**Search debounce:** 300ms. Standard.

### D2. URL-as-state via Next.js `useSearchParams`, NOT a library

**Decision:** Read and write filter state via `useSearchParams` and `router.push`. No library (`nuqs`, `next-usequerystate`, etc.) for v1.

**Why no library:** The state surface is tight (q, tier, type, sort). Wrapping it in a library is two extra deps and an opinion we don't need. If state grows complex, revisit.

**State shape:**
```
/analyses?q=acme&tier=high&type=portfolio&sort=score-desc&cursor=eyJpZCI6...
```

Empty values omit the param (no `?q=` for an empty search). Cursor is base64-encoded JSON.

### D3. Help tooltips driven by a content registry, not inline strings

**Decision:** A single `frontend/src/lib/help-content.ts` exports a TypeScript object mapping term keys (e.g., `risk_tier`, `ebitda_tree`, `value_lever`) to short HTML/markdown explainers. The `<HelpTooltip term="risk_tier">` component looks up the content and renders the ⓘ icon + tooltip popover.

**Why a registry:** Content reused across surfaces (Risk Tier label appears on Analyses, Analysis detail, Dashboard). One source of truth means edits propagate. Also makes copy review easier — one file to read.

**Tooltip mechanism:** Hover on desktop, tap on touch (use a small library like `@radix-ui/react-tooltip` if not already in deps; otherwise a hand-rolled focus-trap-aware popover).

### D4. Bulk actions: shift-click range select, sticky toolbar, single bulk delete v1

**Decision:** Checkbox column on the left of the analyses table. Click a checkbox to toggle one row; shift-click another to select the range between (Linear/Gmail pattern). Selected count appears in a sticky bottom toolbar with "Delete N" and "Cancel" buttons. The Delete button uses Toast Undo (Tier 1 dependency).

**Why only delete v1:** Bulk delete is the highest-utility action today. Bulk re-analyze, bulk tag (when tags exist), bulk export are easy follow-ons once the toolbar pattern is in place.

**Edge cases:**
- Selecting items across pages (if pagination is "Load More" not "page-by-page") — selection persists.
- Selecting items not currently visible (filtered out after filter change) — selection clears on filter change to prevent surprise.

### D5. Relative time component with hydration-safe rendering

**Decision:** New `<RelativeTime value={isoString} />` component. Uses `date-fns/formatDistanceToNow`. Renders the literal absolute time on first server render; client-side effect swaps to relative on hydration (avoids hydration mismatch from "now" being different on server vs client).

**Hover affordance:** native `<time title={absoluteFormatted}>` element so the absolute time is a browser-default tooltip. No custom popover needed.

**Why date-fns:** Tree-shakable, already common in the React ecosystem. If `dayjs` is already a dep (check), use that for consistency. Either is fine; pick whichever is already in `package.json`.

### D6. Activity feed via projection, not a new events table

**Decision:** `GET /api/activity` projects events from existing DynamoDB records (scan creates, completes, deletes; analysis completes; member invites/joins). For v1 the response is computed at request time by scanning recent records and producing event-shaped DTOs. No persistent events table.

**Why no events table:** Premature. Adds a write path everywhere. Projection at read time is "good enough" for v1 with the right caching and the small data set today. When projection becomes too slow (>500ms), we add an events table and a write-side projection.

**Polling cadence:** 30 seconds. Cheap; doesn't need real-time.

**UI shape:** Sidebar panel (collapsed by default, expand to view; bell icon with unread badge). When collapsed shows count of new events since last view. Click to expand and mark read.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **URL-as-state migration breaks existing bookmarks.** | Empty params = same as today. No bookmarks should change. Test with a representative bookmark before merge. |
| **Server-side search performance at 10k+ rows.** | Today's analyses query already paginates via DynamoDB cursors. Adding `contains` filter on `company_name` is O(scan). Acceptable up to 5k; if dataset grows, switch to a search index (OpenSearch or DynamoDB streams → Lambda → search index). |
| **Bulk delete cascade surprise.** | Toast message must be explicit: "Deleted 8 analyses + their reports. Undo?" — same pattern as scan-delete in Tier 1. |
| **Relative time hydration mismatch.** | Server renders absolute time; client effect swaps to relative on mount. Acceptable cost: a 1-frame absolute-time flash on first paint. Alternative is `suppressHydrationWarning` which masks the issue. |
| **Activity feed projection cost grows linearly with org size.** | Add a hard limit (last 100 events shown). Memoize projection per org with a 30s TTL cache. Move to events table when projection > 500ms p95. |
| **Help tooltip content drift.** | Single registry file; add a markdown table to `docs/` that mirrors the content for non-engineering review. Lightweight. |

## Migration Plan

No data migration. All new endpoints additive. Deploy procedure:

1. **Pagination + URL-state + server-side search** — large refactor, ship as one focused PR. Risk: changes the analyses-page experience in a noticeable way; communicate to current users.
2. **Help tooltips** — small, ship anytime after Tier 1.
3. **Relative timestamps** — single util, ~30 places to update. Ship as one PR or split if reviewers want smaller chunks.
4. **Bulk actions** — depends on Tier 1 Toast. Ship after Toast lands.
5. **Activity feed** — backend endpoint + frontend panel. Ship last; the most novel and benefits from the rest landing first.

Rollback: each PR is independent; revert the merge commit. URL-as-state has the only backward-compat concern — empty URL params keep working, so old bookmarks are safe.

## Open Questions

1. **Numbered pagination or "Load More"?** Numbered is more discoverable; Load More is simpler for cursor-based backends. Pick during impl based on whether DynamoDB cursors can be made bidirectional cheaply.
2. **Activity feed: panel or full route?** Sidebar panel for v1 (collapsible); promote to `/activity` route if usage warrants.
3. **Bulk actions for scans, not just analyses?** The proposal scopes to analyses; scans are a smaller list and less likely to need bulk delete. Defer.
4. **Search hotkey on /analyses — is it `/` (Tier 1 shortcut) or also Cmd-K?** Both work today; the focus-search shortcut already lives in Tier 1's keyboard-shortcuts spec. No conflict.
