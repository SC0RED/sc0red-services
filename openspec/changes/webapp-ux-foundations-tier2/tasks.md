## 1. Pagination + URL-as-state + server-side search on /analyses

> **Status: deferred until row count justifies it.** At today's data volumes
> the existing client-side approach is fine; this group ships when a real
> customer's analyses page begins to feel slow (or when an org passes ~200
> analyses, whichever comes first). The other Tier 2 groups do NOT depend
> on this work and may ship in any order before it.


- [ ] 1.1 Backend: extend `handle_list_analyses` in `backend/src/handlers/analysis_handlers.py` to accept a `q` query param. Implement fuzzy-substring match over `company_name` and `industry` (use lower-case `contains` for v1). Return-shape unchanged otherwise.
- [ ] 1.2 Backend unit tests for `?q=`: matches by name, by industry, case-insensitive, empty `q` returns all, paginates correctly when combined with `limit` + `cursor`.
- [ ] 1.3 Frontend: refactor `frontend/src/app/(authenticated)/analyses/page.tsx` to read filter state from `useSearchParams`. Initial mount uses URL params to determine query/filter/sort.
- [ ] 1.4 Frontend: refactor `AnalysesTable.tsx` to fetch via cursor pagination — initial fetch with `limit=50`, "Load More" button when `cursor` is present, replaces results when `q` changes.
- [ ] 1.5 Frontend: search input debounces 300ms before firing the next request; debounce + URL update happen together (single navigation per resolved query).
- [ ] 1.6 Frontend: tier and type filters + sort apply client-side over the loaded slice (no backend round-trip for these). Selection state clears on `q` change.
- [ ] 1.7 Vitest tests: search debounces, URL updates with q/tier/type/sort, refresh preserves filters, "Load More" appends results, search clears prior results.
- [ ] 1.8 Backend pytest: `?q=` integration tests with seeded data.

## 2. Domain tooltips

- [ ] 2.1 Create `frontend/src/lib/help-content.ts` with the registry: keys for `risk_tier`, `risk_score`, `ebitda_tree`, `value_lever`, `active_lever_filter`, `industry`, `impact_rating`. Each entry has a 1-2 sentence explainer.
- [ ] 2.2 Build `frontend/src/components/ui/HelpTooltip.tsx` (`<HelpTooltip term="risk_tier" />`). Renders a small ⓘ icon with a popover on hover/focus/tap. ARIA: `role="tooltip"` + `aria-describedby` association.
- [ ] 2.3 Wire ⓘ tooltips into the analyses table column headers (Risk Score, Risk Tier, Industry).
- [ ] 2.4 Wire ⓘ tooltips into the analysis detail page (EBITDA Tree heading, Value Lever badges, Impact Rating).
- [ ] 2.5 Wire ⓘ tooltips into the opportunities list (Value Lever, Impact Rating).
- [ ] 2.6 Vitest: tooltip renders on hover, on focus (keyboard), on tap (touch); content matches registry; reduced-motion path renders without slide animation.
- [ ] 2.7 Maintain a markdown mirror at `docs/help-content.md` so non-engineers can review copy. Add an audit script (or pre-commit) to verify the markdown matches the registry.

## 3. Bulk actions on analyses

- [ ] 3.1 Add a checkbox column to `AnalysesTable.tsx`. Header checkbox toggles all visible. Row checkboxes toggle individual rows.
- [ ] 3.2 Implement shift-click range selection (track `lastClickedIndex` in selection state).
- [ ] 3.3 Build `frontend/src/components/ui/BulkActionsBar.tsx` — sticky bottom bar that appears when selection is non-empty. Shows "N selected" and a "Delete N" button, plus a "Clear" affordance.
- [ ] 3.4 Wire "Delete N" to Toast Undo (Tier 1 dependency): on click, toast appears with "Deleted N analyses. Undo?" and 5s window; rows visually disappear immediately; DELETEs fire after window expires.
- [ ] 3.5 Selection clears on filter/search change and on navigation away.
- [ ] 3.6 Vitest: header checkbox toggles all visible, row checkbox toggles individual, shift-click selects range, bulk delete fires DELETE for each id after window, undo cancels (no DELETEs fire), selection clears on filter change.

## 4. Relative timestamps

- [x] 4.1 Confirm date library: `date-fns` vs `dayjs` already in `frontend/package.json`? Use whichever is present; otherwise add `date-fns` (smaller). — Added `date-fns@^3.6.0`; neither was previously installed.
- [x] 4.2 Build `frontend/src/components/ui/RelativeTime.tsx`: renders absolute time on SSR, swaps to relative on client mount via `useEffect`. Native `<time title={absolute}>` element so absolute is the browser tooltip. — SSR uses a deterministic UTC formatter (`Apr 27, 2026`) so server and client produce identical HTML regardless of process timezone, avoiding hydration mismatches without needing `suppressHydrationWarning`.
- [x] 4.3 Audit the codebase for raw timestamp renders (`toLocaleString`, `toISOString`, raw API timestamp strings displayed to users in `(authenticated)`). Replace each with `<RelativeTime value={...} />`. — Three render sites found and replaced: `AnalysisRow` analyzedAt cell, dashboard recent-analyses analyzedAt, dashboard recent-scans createdAt. AnalysisDetail / TeamView / PortfolioCard reference these fields but don't currently display timestamps.
- [x] 4.4 Surfaces to update: AnalysesTable analyzedAt column, dashboard recent analyses + recent scans, AnalysisDetail header, Portfolio scan dates, team page member join dates. — Updated all surfaces that currently render a timestamp. Surfacing timestamps where they're not currently shown (analysis-detail header, portfolio cards, team join dates) is deferred — net-new UI not in scope for §4.
- [x] 4.5 Vitest: SSR shape = absolute, client shape = relative, "just now" for <30s, "3 hours ago" for 3h, hover shows absolute via title attribute. — 13 tests, including SSR via `react-dom/server.renderToString`, timezone-independence assertion, and a re-tick test that advances fake timers.

## 5. Activity feed

- [ ] 5.1 Backend: new handler `handle_get_activity` in a new `backend/src/handlers/activity_handlers.py`. Projects events from existing DynamoDB records (scan creates/completes/deletes, analysis completes/failed/deletes, member invites/joins). Cursor-paginated.
- [ ] 5.2 Backend: design event DTO shape (`type`, `actor: {id, name}`, `target: {id, name, type}`, `timestamp`, `summary`). Document in `docs/api/` or in the handler docstring.
- [ ] 5.3 Backend: register `GET /api/activity` in the API gateway router. Org-scoped (only events for the user's org).
- [ ] 5.4 Backend pytest: project covers each event type; org isolation; cursor pagination edge cases; handles missing records (e.g., event references deleted target).
- [ ] 5.5 Frontend: `<ActivityPanel />` component — bell icon in sidebar with unread badge, opens to a list of recent events. Polls `/api/activity` every 30 seconds while open.
- [ ] 5.6 Frontend: each event row renders actor name + action verb + target link + relative timestamp (uses `<RelativeTime>` from §4).
- [ ] 5.7 Frontend: "last viewed" timestamp persisted to localStorage; unread count = events with timestamp > last_viewed.
- [ ] 5.8 Vitest: panel renders events, unread badge reflects count, opening clears badge, polling re-fetches at interval.

## 6. Quality gates

- [ ] 6.1 `cd backend && uv run ruff check src/` clean.
- [ ] 6.2 `cd backend && uv run pyright src/` no new errors vs baseline.
- [ ] 6.3 `cd backend && uv run pytest tests/ -q` all green; coverage ≥ 95%.
- [ ] 6.4 `cd frontend && npm run lint && npx tsc --noEmit && npm test` all clean.
- [ ] 6.5 Architecture-reviewer agent run on the combined diff per task group. Resolve all CRITICAL + MEDIUM findings.
- [ ] 6.6 E2E suite (`E2E_MODE=full`) — no regressions. New E2E test for "URL filter persists across reload."

## 7. Rollout + PR

- [ ] 7.1 PR per task group (1, 2, 3, 4, 5). Each ships independently.
- [ ] 7.2 Pagination + URL-state + server-side search PR is **deferred** (see §1 status note) — ships when row count makes it necessary. Other items ship in any order independently.
- [ ] 7.3 Activity feed ships last (most novel; benefits from learning from the rest).
- [ ] 7.4 Self-review on each PR following the post-#182 conventions: assert on rendered hrefs and `data-state`-style attributes, never just on text.
