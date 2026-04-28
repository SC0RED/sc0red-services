## Context

Janus is a SaaS for PE firms. The webapp serves a power-user audience (analysts moving through 100s of companies, jumping between scans and portfolios on a daily basis). Today's app has the right bones — design tokens, primitive components, error boundaries, web vitals — but it's missing the daily-use UX patterns that good SaaS apps treat as table stakes.

This change captures five Tier 1 items, each independently shippable, packaged together so the foundation lands cohesively. The bundling matters because several items share infrastructure (e.g., the keyboard handler used by Cmd-K is reused by the shortcuts modal and the `Esc` close-any-modal behavior; Settings depends on Toast for "Profile saved" feedback).

```
DEPENDENCY GRAPH (within this change)

    Toast ──────────┬──> Mutation wiring (delete, invite, re-analyze)
                    │
                    └──> Settings page (save feedback)

    Cmd-K ──────────┬──> Keyboard shortcuts (shared global handler)
                    │
                    └──> Palette opens to /settings, /scan/new, /analyses, etc.

    Provenance ──── (independent of the rest)
```

The independent item is the analyses→portfolio cross-reference, which is the smallest by far. It can ship first (afternoon-sized PR) to land a quick visible win.

## Goals / Non-Goals

**Goals:**
- Every mutation in the app gives the user an explicit "this happened" signal via toast.
- Power users can navigate the entire app from the keyboard.
- Users have a clear destination for "where do I change my settings."
- An analyst looking at an analysis can always answer "which scan did this come from?" without using the back button or the URL.
- Each item is shippable as its own PR; a half-shipped Tier 1 leaves the app in a coherent state.

**Non-Goals:**
- Persistent notifications inbox — Toast is for ephemeral feedback. The org-wide "activity feed" is Tier 2.
- Server-side search powering Cmd-K — for now, palette searches over the analyses list already in memory + a fixed set of actions. When `/analyses` has 1000+ rows, palette search will need a backend; that's Tier 2 work.
- Light mode toggle in the Settings page — this is Tier 3 polish. The Settings page lays out a section heading "Appearance" but contains no toggles yet (or omits the section entirely; decided during implementation).
- Audit log / "who did what" surfacing — Tier 3.
- Refactoring the existing logout placement — wherever logout lives today (top-bar / sidebar bottom / settings dropdown), this change consolidates it but does not redesign the logout UX.

## Decisions

### D1. Toast bottom-right, vertically stacked, role-driven a11y

**Decision:** Toasts render in the bottom-right viewport corner. Multiple toasts stack vertically (newest on top of the stack). Success/info auto-dismiss after 4s; error toasts require explicit dismiss. `role="status"` for success/info, `role="alert"` for errors. Slide-in animation respects `prefers-reduced-motion` (collapses to instant).

**Why bottom-right:** Linear, Vercel, GitHub, Stripe — the well-loved ones converged on this corner. Top-right competes with the page header. Top-center is intrusive. Bottom-left is unfamiliar. Bottom-right is the user's peripheral vision while reading top-down.

**Why error doesn't auto-dismiss:** A 4-second flash for "Failed to delete" means a user who looked away misses both the failure AND any actionable text in the toast. Errors stick until acknowledged; the close button is the primary affordance.

**Alternatives considered:**
- *Top-right (Toast / Sonner default).* Rejected — competes with the existing route progress bar at the top.
- *Auto-dismiss everything with longer time for errors.* Rejected — silent failure of the auto-dismiss timer (e.g., browser tab loses focus) means lost errors.

### D2. Cmd-K via `cmdk` (Vercel's package), not a from-scratch implementation

**Decision:** Use the `cmdk` library (`@vercel/cmdk` family — actually the `cmdk` npm package). Build the palette over its primitives, not over `headless-ui` or kbar.

**Why:** `cmdk` is small (~3 KB gzipped), unstyled, accessibility-correct out of the box, used by Vercel's own dashboard, and matches React 18+ semantics. Building from scratch costs days; kbar has heavier opinions about command structure that don't fit the simpler list-based model we want.

**Alternatives considered:**
- *kbar* — more featureful (nested commands, action chaining), but more opinionated and heavier; we don't need its features yet.
- *Build minimal* — ~200 lines of code for a fuzzy search modal with focus trap and arrow-key navigation. Saves a dependency but loses time and a11y battle-testing.

### D3. Keyboard shortcuts: GitHub/Linear conventions, not custom

**Decision:** `g d` / `g a` / `g s` / `g t` for navigation (Dashboard / Analyses / Scan-new / Team). `?` opens a shortcuts modal. `Esc` closes any modal. `/` focuses search on the analyses page. `Cmd-K` opens command palette.

**Why match conventions:** Power users come from other tools. Reusing their muscle memory is a force multiplier. Inventing our own scheme is paying for friction we don't need.

**Conflict avoidance:**
- `Cmd+S`, `Cmd+P`, `Cmd+R`, `Cmd+W`, `Cmd+T` reserved (browser).
- `Cmd+/` (Linear's shortcuts modal) is also browser-friendly but `?` is more universal.
- `g`-prefix nav requires a chord (g pressed, then d within ~1s). Standard pattern.

### D4. Settings page is read-only for v1 except logout / org_id copy

**Decision:** Profile section displays name + email but doesn't allow editing yet (Cognito hosts those forms; we link to them later). Org section shows org_id with a copy-to-clipboard button + role badge. No theme toggle in v1 (Tier 3). Logout consolidated here.

**Why:** Editing profile fields means new API endpoints, validation, server-side error handling — a feature on its own. For Tier 1, the Settings page existing as a destination matters more than what's editable in it.

**Alternatives considered:**
- *Ship Settings page only after profile editing works.* Rejected — Settings page existing is the table-stakes piece; editability is incremental polish on top.
- *Defer Settings page entirely until we have things to edit.* Rejected — users today have no destination for "logout" or "what's my org_id?" beyond hunting through the UI.

### D5. Provenance link UX: badge becomes a link, detail page gets a subtle line

**Decision:**
- `/analyses` rows: the existing "Portfolio" badge wraps in `<Link href={`/portfolio/${scanId}`}>` for portfolio-type rows. Standalone rows render the badge as plain text (no link). Hover affordance same as other links.
- `/analysis/{id}`: render `Part of: {scan_name}` as small secondary text near the company name (top of the page). Click navigates to `/portfolio/{scanId}`. Only renders for `scanType === "portfolio"`. Standalone analyses get nothing (the analysis IS the scan).

**Why this shape:** Both surfaces show the same information (this analysis belongs to a portfolio scan). The badge-as-link on the list is recognition, the line on the detail page is reference — two different needs. A scan name (not the type) is the human-readable handle, so we use that on the detail page.

**Alternatives considered:**
- *Add a "Scan" column to the analyses table.* Rejected — the table is already wide; the existing badge is repurposed for free with no layout change.
- *Render the provenance only on the detail page, not the list.* Rejected — the list is where users decide which analysis to click; provenance signal helps them navigate without entering the detail page first.

### D6. Toast Undo: 5-second commit window, no server-side soft-delete

**Decision:** Destructive actions (delete analysis, delete scan) trigger a "Deleted. Undo?" toast with a 5-second window. Within the window, click "Undo" cancels the deletion. The actual delete API call is delayed until window expiry (or immediate on toast dismiss).

**Why optimistic-deferred-commit, not optimistic-with-rollback:** With deferred commit, undo is a no-op (cancel the timer); the API call never happens. With rollback, undo means re-creating the record server-side — needs a re-create endpoint, race conditions if other clients see the stale record, etc.

**Alternatives considered:**
- *Server-side soft-delete with explicit restore.* Rejected — adds DB schema complexity (deletion timestamp, GC job, cascading restore semantics). Worth doing later if undo timeout grows beyond 5s.
- *Skip Undo, keep the existing confirm dialog.* Rejected for delete — the confirm-first pattern is slow for users who already know what they're deleting; toast-undo is faster AND safer (more visible in the user's eyeline).

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **`cmdk` library bundle bloat.** | At ~3 KB gzipped it's negligible; bundlephobia confirms. If we ever audit and find it grew or we want one less dependency, the migration to a hand-rolled palette is ~200 lines. |
| **Keyboard shortcuts collide with users' OS-level or extension shortcuts.** | Only register shortcuts when no input/textarea/contenteditable is focused. Use the `keydown`/`keyup` event with explicit checks (not document-level catch-all). Standard pattern. |
| **Toast positioning interferes with the route progress bar.** | They occupy different corners (progress is top, toasts are bottom). Stack overflow only happens with many concurrent toasts — cap at 5 visible, queue the rest. |
| **Settings page exists but is mostly empty.** | Section headings hint at what's coming ("Profile", "Org", "Appearance — coming soon"). For v1 the destination existing matters more than fullness. |
| **Provenance link in the analyses list — clickable badges may be unfamiliar.** | Use the same hover affordance as other table links; the badge already has color. If user research shows confusion, fallback is a separate "Scan" column (Tier 2 polish). |
| **Toast Undo only works while the user keeps the page open.** | A user who deletes and immediately closes the tab loses Undo. This is acceptable — they got the safety window if they wanted it. Server-side soft-delete is the next-level fix (deferred). |
| **#182's failed-card regression class.** | Every test asserting on navigation MUST check the rendered `<a href>` value, not just the link text. The new test convention from PR #183 is the template. Apply it to all five items in this change. |

## Migration Plan

No data migration. All changes are additive UI / new components. Deploy procedure:

1. Ship Provenance link first (smallest, no shared infra) — afternoon-sized PR.
2. Ship Toast component + provider + mutation wiring — moderate, ~2 days.
3. Ship Settings page + sidebar entry — moderate, ~1 day.
4. Ship Cmd-K palette + keyboard shortcuts together — largest, ~3 days.

Each item rolls back independently via `git revert`. There are no schema or API contract changes to undo.

The order matters because Settings (#3) uses Toast (#2) for save feedback, but if Toast hasn't shipped yet, Settings can ship without save feedback (read-only page, no saves). Cmd-K (#4) reuses the keyboard handler infrastructure built for shortcuts; ship them as one PR.

## Open Questions

1. **Logout placement — settings dropdown or sidebar bottom?** Verify current location and pick during item 4 implementation. Both are common; settings dropdown matches Linear/Vercel, sidebar bottom matches Notion/Slack.
2. **Cmd-K data source for "Companies" search — fetch fresh on open or use last-loaded list?** Probably last-loaded for v1 (simpler, matches how the analyses page already works). When server-side search lands in Tier 2, palette switches to the server.
3. **Toast Undo for `delete-scan` cascades — what gets restored on undo?** Currently scan deletion cascades to all analyses. Deferred-commit means no actual delete happens until window expiry, so undo is clean. But the "Deleted scan + 8 analyses" message should be explicit about scope so users know what they're un-doing.
