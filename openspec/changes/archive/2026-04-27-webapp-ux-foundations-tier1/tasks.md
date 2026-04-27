## 1. Provenance link (smallest, ships first)

- [x] 1.1 Wrapped the existing "Portfolio" badge in `AnalysisRow.tsx` (via a small `ScanTypeBadge` sub-component) in a `<Link href={`/portfolio/${scanId}`}>` for portfolio rows; standalone rows render the badge as plain text; click propagation stopped defensively.
- [x] 1.2 Added a "Part of: {scan_label}" line below the company name in `AnalysisHeader.tsx` for portfolio analyses; also enhanced the breadcrumb to show the scan label (was just "Portfolio") and gated both on `scanType === 'portfolio'` (fixed pre-existing bug where the breadcrumb showed for any scanId, including standalone scans).
- [x] 1.3 Backend `handle_get_analysis` now joins to the parent scan record and returns `scanType` (was missing entirely) and `scanSourceUrl`. `handle_list_analyses` now also includes `scanId` on each row so the analyses table can build the badge link.
- [x] 1.4 Vitest tests for the analyses-list badge: 4 new tests asserting on rendered `<a href>` — portfolio links to /portfolio/{scanId}, standalone has no link, missing-scanId portfolio renders without crash, multiple rows link to their own scans.
- [x] 1.5 Vitest tests for the analysis-detail provenance: 5 new tests covering portfolio-renders-Part-of, standalone-renders-nothing (regression guard), no-scanId-renders-nothing, fallback-when-scanSourceUrl-empty, URL-prettification-strips-protocol-and-trailing-slash.

Shipped via **PR #184** (commit 2c682e2). FailedAnalysisView extension landed as **PR #186** (commit af61146).

## 2. Toast component foundation

- [x] 2.1 Built `frontend/src/components/ui/Toast.tsx` (single file containing item + provider + viewport). Variants: success / error / info / loading. Bottom-right portal-style viewport. Stack vertically. Auto-dismiss 4s for success/info; error and loading persist.
- [x] 2.2 `useToast()` hook exposes `success(msg, desc?)`, `error(msg, desc?)`, `info(msg, desc?)`, `loading(msg, desc?) → toastId`, plus `update(toastId, fields)` and `dismiss(toastId)`. Hook throws if used outside the provider.
- [x] 2.3 Mounted `<ToastProvider>` in the **root** `frontend/src/app/layout.tsx` (decided to mount at root rather than authenticated layout — toast doesn't render on its own and the API may be useful from /login etc; harmless to expose globally).
- [x] 2.4 Single shared `@keyframes toast-slide-in` in `globals.css`. Animates `opacity` + `transform: translateY` only (GPU-cheap). The existing global `prefers-reduced-motion: reduce` rule collapses animation-duration → toasts appear at the keyframe's `to` state instantly.
- [x] 2.5 ARIA: `role="status"` for success/info/loading (polite), `role="alert"` for error (assertive). Close button has `aria-label="Dismiss notification"` and visible focus ring.
- [x] 2.6 15 vitest tests covering: each variant + role, auto-dismiss for success/info, persistence for error/loading, close-button dismiss, dismiss(id) only removes matching toast, update() promotes loading → success in place (no duplicate), stacking, viewport aria-live, useToast outside provider throws.

Shipped via **PR #185** (commit 6b0253f).

## 3. Toast Undo + mutation wiring

- [x] 3.1 Added `toast.undo({ message, onCommit, onUndo, durationMs? })` API: returns a toast that has an Undo button visible for `durationMs` (default 5000); if Undo is clicked, `onUndo()` runs and `onCommit` is NEVER called; otherwise `onCommit` runs after the timer. Close button treated as commit-early (per design D6).
- [x] 3.2 Wired `DeleteAnalysisButton` to `toast.undo`: replaced the inline confirm-then-Yes/No flow with a 5s deferred-commit window. Click → toast → Undo cancels (no DELETE) or commit fires DELETE + `router.refresh()` / `router.push(redirectTo)`. Error toast on failure.
- [x] 3.3 Wired `DeleteScanButton` similarly. Cascade message uses `scan.totalCompanies` (not `completedCount` — that would underreport for in-flight scans). Singular/plural ("1 analysis" vs "N analyses") handled.
- [x] 3.4 Team invite + resend route through `toast.success` / `toast.error`, replacing inline `<div role="alert">` blocks. Revoke + remove also converted to `toast.undo` with optimistic-remove + restore-on-undo.
- [x] 3.5 Re-analyze: `toast.loading('Re-analyzing...')` → `toast.update` to success on completion or error on failure. AbortError dismisses the toast (caught a real bug — both poll-loop exit paths now dismiss; the original code leaked the loading toast).
- [x] 3.6 Vitest tests covering each mutation: toast appears immediately, no DELETE before window, DELETE fires after window, Undo cancels (no API call), error path. 19 net new tests across DeleteAnalysisButton, DeleteScanButton, TeamView, AnalysisDetail.

Shipped via **PR #187** (commit 13cc5db). The PR also adds a backend `totalCompanies` field on the dashboard `recentScans` response.

## 4. Settings page

- [x] 4.1 Verified current logout placement (sidebar bottom — icon button next to user info card). Kept the icon as the always-available shortcut; Settings page adds a dedicated "Sign out" button as the destination path. Same `signOut({ callbackUrl: '/login' })` call site.
- [x] 4.2 New route `frontend/src/app/(authenticated)/settings/page.tsx` (server component shell) and `SettingsView.tsx` (~210 lines).
- [x] 4.3 Profile section: read `name` and `email` from NextAuth session (`useSession`); rendered read-only with a clarifying note about Cognito-hosted password change via the Forgot Password flow.
- [x] 4.4 Org info section: `orgId` rendered in monospace with a copy-to-clipboard button that fires a success toast and shows a "Copied" confirmation for 1.5s. `role` rendered as a Badge with default-deny fallback to `'member'` for unknown roles.
- [x] 4.5 "Sign out" button using NextAuth `signOut({ callbackUrl: '/login' })`.
- [x] 4.6 New sidebar entry "Settings" in `frontend/src/components/sidebar/navItems.tsx` with a gear icon. Slotted after "Team".
- [x] 4.7 10 vitest tests covering: name/email render from session, dash placeholders for missing fields, orgId monospace + Copy button, role badge with fallback, Copy hidden when orgId empty, clipboard write success + toast + visual "Copied" state, clipboard write failure → error toast, Sign out triggers signOut with correct callback. Plus 1 sidebar nav test pinning the `/settings` href.

Shipped via **PR #188** (commit 3c21143).

## 5. Cmd-K + global keyboard shortcuts

- [x] 5.1 Installed `cmdk` dependency (~3 KB gzipped).
- [x] 5.2 Built `frontend/src/components/ui/CommandPalette.tsx` over cmdk primitives. Sources: companies (from `/api/analyses`), portfolios (from `/api/dashboard` recentScans, filtered to `type === 'portfolio'`), actions (static list). Fuzzy search. Arrow-key nav. Focus trap. Lazy-fetch + per-session cache; cache only marked populated when at least one source succeeds (transient failures recover on next open).
- [x] 5.3 Built `frontend/src/components/GlobalShortcuts.tsx` (single-file orchestrator instead of a hook — clearer ownership of palette + shortcuts-modal state). Registers Cmd+K / Ctrl+K (toggle palette), `?` (open help modal), `g d`/`g a`/`g s`/`g t`/`g c` chords with 1s window, `/` (focus search on /analyses), `Esc` (close topmost modal).
- [x] 5.4 Mounted the shortcut handler + both modals in `frontend/src/app/(authenticated)/layout.tsx` so they're authenticated-only.
- [x] 5.5 Built `frontend/src/components/ui/KeyboardShortcutsModal.tsx` listing all shortcuts grouped by category (Search / Navigation / Modal). Triggered via the `?` shortcut.
- [x] 5.6 Guard `isTypingTarget` checks `INPUT`/`TEXTAREA`/`SELECT`/`contentEditable` against `event.target`. All shortcuts (except Cmd+K) suppressed while typing. Cmd+K allowed everywhere per macOS/SaaS convention.
- [x] 5.7 19 vitest tests covering: Cmd+K opens, Ctrl+K opens, Cmd+K toggles closed, ? opens help modal, ? does NOT open while typing in input, each g chord navigates, chord resets after 1s, chord ignored while typing, unknown second-key resets, / focuses search on /analyses, / does nothing on other pages, Esc closes palette, Esc closes shortcuts modal, Esc with no modal does not crash, chord suppressed while palette is open.

Shipped via **PR #189** (commit af93a0b). Also added `ResizeObserver` and `Element.prototype.scrollIntoView` stubs to `vitest.setup.ts` (cmdk requires both; jsdom ships neither). The `prettifyUrl` helper was extracted to `frontend/src/lib/utils/url.ts` and is shared with `AnalysisHeader`.

## 6. Quality gates

- [x] 6.1 `cd frontend && npm run lint` — clean across every PR (#184–#189).
- [x] 6.2 `cd frontend && npx tsc --noEmit` — clean across every PR.
- [x] 6.3 `cd frontend && npm test` — all green; total grew from 455 (pre-Tier-1) to 526 (post-Tier-1) — 71 net new tests.
- [x] 6.4 Architecture-reviewer agent ran on every PR's diff. Findings resolved before merge (notably: PR #184 added 3 backend tests for the new scan-provenance path; PR #187 fixed the AbortError-dismiss bug surfaced by the abort-test reviewer recommendation; PR #189 fixed the palette race condition + first-open-failure cache-stuck bug).
- [x] 6.5 E2E suite continues to pass (45/45 from `portfolio-scan-stable-cards`'s test addition; no regressions across Tier 1 PRs).
- [x] 6.6 Manual smoke deferred to testing-environment verification (PR #190 promotes development → testing post-Tier-1).

## 7. Documentation + PR

- [x] 7.1 In-code docstrings carry the conventions (each component has a header comment explaining purpose + cross-references). A dedicated CLAUDE.md update was deferred — usage patterns are self-documenting via the `useToast` typed API and the `<CommandPalette>` / `<KeyboardShortcutsModal>` props.
- [x] 7.2 Shipped as 5 separate PRs (one per task group): #184, #185, #187, #188, #189. Plus #186 for the FailedAnalysisView pre-existing bug fix that fell out of #184's review.
- [x] 7.3 Every PR carried a self-review with explicit assertion conventions (rendered `<a href>` over text, `data-state` attributes, etc.). Multiple real bugs caught via self-review (FailedAnalysisView regression in #184 → #186; AbortError leak in #187 review; race + empty-cache bugs in #189 review).
