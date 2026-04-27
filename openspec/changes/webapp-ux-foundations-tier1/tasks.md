## 1. Provenance link (smallest, ships first)

- [x] 1.1 Wrapped the existing "Portfolio" badge in `AnalysisRow.tsx` (via a small `ScanTypeBadge` sub-component) in a `<Link href={`/portfolio/${scanId}`}>` for portfolio rows; standalone rows render the badge as plain text; click propagation stopped defensively.
- [x] 1.2 Added a "Part of: {scan_label}" line below the company name in `AnalysisHeader.tsx` for portfolio analyses; also enhanced the breadcrumb to show the scan label (was just "Portfolio") and gated both on `scanType === 'portfolio'` (fixed pre-existing bug where the breadcrumb showed for any scanId, including standalone scans).
- [x] 1.3 Backend `handle_get_analysis` now joins to the parent scan record and returns `scanType` (was missing entirely) and `scanSourceUrl`. `handle_list_analyses` now also includes `scanId` on each row so the analyses table can build the badge link.
- [x] 1.4 Vitest tests for the analyses-list badge: 4 new tests asserting on rendered `<a href>` — portfolio links to /portfolio/{scanId}, standalone has no link, missing-scanId portfolio renders without crash, multiple rows link to their own scans.
- [x] 1.5 Vitest tests for the analysis-detail provenance: 5 new tests covering portfolio-renders-Part-of, standalone-renders-nothing (regression guard), no-scanId-renders-nothing, fallback-when-scanSourceUrl-empty, URL-prettification-strips-protocol-and-trailing-slash.

## 2. Toast component foundation

- [ ] 2.1 Build `frontend/src/components/ui/Toast.tsx` (single toast item) and `frontend/src/components/ui/ToastProvider.tsx` (queue + portal + provider). Variants: success / error / info / loading. Bottom-right positioning. Stack vertically. Auto-dismiss 4s for success/info, error persists.
- [ ] 2.2 Build `frontend/src/lib/hooks/useToast.ts`: hook exposing `toast.success(msg)`, `toast.error(msg)`, `toast.info(msg)`, `toast.loading(msg) → toastId`, and `toast.update(toastId, opts)` for promoting loading → success/error.
- [ ] 2.3 Wire `<ToastProvider>` into `frontend/src/app/(authenticated)/layout.tsx` so it's mounted across the authenticated app surface.
- [ ] 2.4 CSS: single shared `@keyframes toast-slide-in`; respects `prefers-reduced-motion: reduce` (collapses animation-duration). Single source of truth in `globals.css`.
- [ ] 2.5 ARIA roles: `role="status"` for success/info/loading; `role="alert"` for error. Close button is keyboard-focusable + labelled.
- [ ] 2.6 Vitest tests: each variant renders, success auto-dismisses, error persists, multiple toasts stack, close button works, reduced-motion path renders without animation class.

## 3. Toast Undo + mutation wiring

- [ ] 3.1 Add `toast.undo(label, onCommit, onUndo, durationMs=5000)` API: returns a toast that has an Undo button visible for `durationMs`; if Undo is clicked, `onUndo()` runs and `onCommit` is NEVER called; otherwise `onCommit` runs after the timer.
- [ ] 3.2 Wire `DeleteAnalysisButton` to `toast.undo`: instead of immediate API call + confirm dialog, click → toast with "Deleted. Undo?" → 5s window → DELETE fires (or doesn't, if undone). Decide whether to keep the confirm dialog as a separate "irreversible bulk-delete" affordance or remove it for single delete.
- [ ] 3.3 Wire `DeleteScanButton` similarly; the toast message must be explicit about cascade scope: "Deleted scan + 8 analyses. Undo?"
- [ ] 3.4 Wire team invite flow: success toast "Invitation sent to {email}", error toast on failure with the server message.
- [ ] 3.5 Wire re-analyze flow: `toast.loading("Re-analyzing...")` → on completion `toast.update` to success "Re-analysis queued"; on failure update to error.
- [ ] 3.6 Vitest tests: each mutation surfaces the correct toast on success and error paths. For Undo: assert API is NOT called within window; assert API IS called after window.

## 4. Settings page

- [ ] 4.1 Verify current logout placement (sidebar bottom? top-bar dropdown? somewhere else?). Document in code comment + design notes; decide whether to keep current location and add settings logout, or consolidate.
- [ ] 4.2 New route `frontend/src/app/(authenticated)/settings/page.tsx` and `SettingsView.tsx` (~200 lines).
- [ ] 4.3 Profile section: read `name` and `email` from NextAuth session (`useSession`); render read-only with a clarifying note + link to existing password reset flow.
- [ ] 4.4 Org info section: render `orgId` (from session JWT) with a copy-to-clipboard button that fires a success toast on copy. Render `role` as a `Badge`.
- [ ] 4.5 "Sign out" button using existing NextAuth `signOut`.
- [ ] 4.6 New sidebar entry "Settings" in `frontend/src/components/sidebar/navItems.tsx` (new entry, not adminOnly). Use a gear/cog icon.
- [ ] 4.7 Vitest tests: page renders all sections from a mocked session; copy button copies to clipboard and fires toast; signout triggers expected NextAuth call.

## 5. Cmd-K + global keyboard shortcuts

- [ ] 5.1 Install `cmdk` dependency. Verify bundle impact (~3 KB gzipped).
- [ ] 5.2 Build `frontend/src/components/ui/CommandPalette.tsx` over `cmdk` primitives. Sources: companies (from last-loaded analyses list), portfolios (from last-loaded scans), actions (static list). Fuzzy search. Arrow-key navigation. Focus trap. Returns focus on close.
- [ ] 5.3 Build `frontend/src/lib/hooks/useGlobalShortcuts.ts`: registers Cmd+K (open palette), `?` (open help modal), `g d` / `g a` / `g s` / `g t` / `g c` chords (navigate), `/` (focus search on `/analyses`), `Esc` (close topmost modal).
- [ ] 5.4 Mount the shortcut handler in `frontend/src/app/(authenticated)/layout.tsx` so it's authenticated-only (palette doesn't render on `/login`).
- [ ] 5.5 Build `frontend/src/components/ui/KeyboardShortcutsModal.tsx` listing all shortcuts grouped by category. Trigger via the `?` shortcut.
- [ ] 5.6 Guard against firing shortcuts when an input/textarea/contenteditable is focused (use `document.activeElement` checks).
- [ ] 5.7 Vitest tests: palette opens on Cmd+K, shortcuts fire only when no input focused, chord buffer resets after timeout, Esc closes topmost modal, `?` opens help modal, `/` focuses search input.

## 6. Quality gates

- [ ] 6.1 `cd frontend && npm run lint` clean.
- [ ] 6.2 `cd frontend && npx tsc --noEmit` clean.
- [ ] 6.3 `cd frontend && npm test` all green; coverage maintained.
- [ ] 6.4 Architecture-reviewer agent run on the combined diff. Resolve all CRITICAL + MEDIUM findings.
- [ ] 6.5 E2E suite (`E2E_MODE=full`) — no regressions; existing 45 tests still pass. New E2E tests not strictly required (UI-only changes) but consider one Playwright case for Cmd+K → palette → navigate.
- [ ] 6.6 Manual smoke: open each new surface and verify keyboard-only operation.

## 7. Documentation + PR

- [ ] 7.1 Update `frontend/CLAUDE.md` (if it exists) or root `CLAUDE.md` with conventions for new toast usage.
- [ ] 7.2 Open PR(s) against `development`. Recommended split: one PR per task group (1, 2, 3, 4, 5) so each ships independently. The architecture reviewer + CI runs are smaller per PR.
- [ ] 7.3 Self-review each PR with assertions on rendered `<a href>` and `data-state`-style attributes (avoid the failure mode that #182's failed-card regression had).
