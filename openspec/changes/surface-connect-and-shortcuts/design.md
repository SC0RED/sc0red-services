## Context

Grounded in the current web app:
- Sidebar nav is `frontend/src/components/sidebar/navItems.tsx` (Dashboard, New Scan, Analyses, Team[admin], Settings, Recently Deleted[admin]), rendered by `DashboardSidebar.tsx`, which has a user footer block (avatar / name / email / sign-out).
- The MCP Connect page shipped at `/settings/connect` (`app/(authenticated)/settings/connect/`); `/settings/connected-apps` already redirects there.
- `GlobalShortcuts.tsx` binds `?` → `KeyboardShortcutsModal` and `⌘K`/`Ctrl-K` → `CommandPalette` (cmdk); nav `g`-chords are gd/ga/gs/gt/gc. Nothing on screen advertises any of this.

This change is pure surfacing — no new pages or backend. It builds on the (still-active, pending-archive) `self-serve-mcp-connect-page` change; that change's page content is unchanged here.

## Goals / Non-Goals

**Goals:**
- Make MCP Connect a first-class, one-click destination that also reads as a feature worth trying.
- Make the shortcuts help and command palette discoverable to both keyboard AND mouse users, unobtrusively.
- Preserve every existing link, route behavior, and modal interaction.

**Non-Goals:**
- No change to the Connect page content, `/api/config`, OAuth, or consent management.
- No new command-palette search sources or new shortcuts beyond the Connect chord.
- No intrusive onboarding (modals, coach-marks, nagging banners) — a nav pill + a dull footer line only.

## Decisions

### Connect → top-level "Connect AI"
- New `navItems` entry `{ href: '/connect', label: 'Connect AI' }`, not admin-only. Placement: below Analyses / near Settings (a setup-adjacent power feature), not competing with the primary work items at the top.
- **Route moves** to `/connect` (`app/(authenticated)/connect/`); `/settings/connect` and `/settings/connected-apps` become redirects to `/connect`. The page component itself is moved as-is.
- Remove the Settings ▸ Connect section (`SettingsView.tsx`) — one home only.
- **`g`-chord**: gd/ga/gs/gt/gc are taken; use a free, mnemonic letter. Preference order: `g i` ("integrations"/"install") or `g m` ("MCP") — pick one in implementation and add it to both `NAV_CHORDS` and the `KeyboardShortcutsModal` navigation list.
- **"New" pill**: a small muted pill on the nav item. Trigger (simplest viable): dismiss on the user's first visit to `/connect`, persisted in `localStorage` (e.g. `sc0red-services.connect-seen`). Rationale: no backend, no per-user server state; "seen the page" is a good enough proxy for "aware of the feature." Trade-off: localStorage is per-device (the pill can reappear on a new browser) — acceptable for an awareness nudge. A fixed sunset date is the fallback if we'd rather not add storage.

### Discoverability affordance (shortcuts + palette)
- A dull, small line in the **sidebar footer**: `⌘K commands · ? shortcuts`, each segment a `<button>` that opens the palette / shortcuts modal respectively. Clickable is the key decision — a keyboard-only "press ?" hint would exclude mouse users and fail the very audience that can't find the shortcut.
- Wiring: the palette/shortcuts open-state currently lives in `GlobalShortcuts`. Expose those open handlers so the footer buttons can trigger them without duplicating modal state — e.g. lift the open-state to a small context/provider that both `GlobalShortcuts` (key handlers) and `DashboardSidebar` (footer buttons) consume, or hoist the modals to the layout with a shared setter. Must preserve the existing `Esc`/precedence behavior (palette > shortcuts) and the "suppress chords while a modal is open" logic.
- Add a **"Keyboard shortcuts"** action to the command palette that opens the help modal (so ⌘K users discover it), reusing the same open handler.
- Keyboard shortcut on the platform: show `⌘K` on macOS and `Ctrl K` elsewhere if the app already detects platform; otherwise `⌘K` is an acceptable universal label (matches the existing modal copy).

### Component size
`DashboardSidebar.tsx` is ~304 lines; adding the footer affordance risks the 360-line limit. Extract the affordance (and possibly the user-footer block) into a small `SidebarFooter` sub-component to stay well under the limit and to test the click-opens-modal behavior in isolation.

## Risks / Trade-offs

- **Shared modal state refactor** — lifting the palette/shortcuts open handlers out of `GlobalShortcuts` is the only non-trivial bit; done wrong it could break `Esc` precedence or the chord-suppression-while-open guard. Mitigation: keep `GlobalShortcuts` as the owner of state and pass setters down (minimal move), with tests asserting Esc precedence and that chords stay suppressed while a modal is open.
- **Nav real estate** — a permanent "Connect AI" item for a mostly-one-time action. Accepted: it doubles as feature awareness, and the sidebar has room. The "New" pill fades after first visit so it doesn't nag forever.
- **"New" pill on a new device** — localStorage per-device means the pill can reappear; harmless for an awareness cue.
- **Route move** — `/settings/connect` → `/connect` changes a URL; mitigated by redirects from both old paths. Deep links and the just-shipped page keep working.
- **Two changes, one PR** — bundling nav + discoverability is deliberate (same sidebar surface, same theme); if review prefers, they split cleanly along capability lines.
