## Why

Two capable features in the web app are effectively hidden, so customers don't discover them:

1. **MCP Connect is buried in Settings.** The self-serve Connect page (query your portfolio from Claude / ChatGPT / Cursor) lives at `/settings/connect` — two levels deep, off the main nav, with no keyboard chord. It's a differentiating feature but reads like a minor setting.
2. **Keyboard shortcuts + command palette are undiscoverable.** `?` opens a shortcuts help modal and `⌘K`/`Ctrl-K` opens a command palette, but **nothing on screen ever says so** — the only way to learn the shortcuts is a shortcut you can't find (the help entry for `?` lives *inside* the modal `?` opens). Mouse-only users have no path in at all.

Both are surfacing problems, not new features — the underlying pages/modals already exist and are tested.

## What Changes

- **Promote Connect to a top-level nav item.**
  - New sidebar entry captioned **"Connect AI"** (the label sells the outcome; "MCP" jargon stays on the page, not the nav). Available to all users (per-user OAuth), not admin-only.
  - Move the page route to `/connect`; **redirect** the old `/settings/connect` and `/settings/connected-apps` → `/connect` so existing links keep working. Page content is unchanged.
  - Remove the Settings ▸ Connect section (single home; no duplicate doorway).
  - Add a navigation `g`-chord for Connect and list it in the shortcuts help modal.
  - Show a small **"New"** pill on the nav item until the user has connected once (or a fixed sunset) to draw the eye without a nagging banner.

- **Make shortcuts + the command palette discoverable.**
  - Add a dull, small, **clickable** affordance in the sidebar footer (by the user/sign-out block): `⌘K commands · ? shortcuts` — each opens its respective modal on click. Clickable so mouse users (and assistive tech) can reach it, not just keyboard users.
  - Add a **"Keyboard shortcuts"** entry to the ⌘K command palette so palette users find the help too.

## Capabilities

### New Capabilities
<!-- None — these surface existing features; the work modifies existing capabilities. -->

### Modified Capabilities
- `authenticated-layout`: the sidebar gains a top-level **Connect** entry (with a "New" pill) and the Connect page moves to `/connect` with redirects from the old Settings routes; the Settings ▸ Connect section is removed.
- `keyboard-shortcuts`: the `g`-chord set gains a Connect destination (listed in the help modal), and shortcuts become discoverable via a persistent, clickable sidebar-footer affordance rather than only through the `?` key.
- `command-palette`: the palette is made discoverable via the same footer affordance (`⌘K`) and gains a "Keyboard shortcuts" action that opens the help modal.

## Impact

- **Frontend only.** Touches `components/sidebar/navItems.tsx`, `components/DashboardSidebar.tsx` (footer affordance), `components/GlobalShortcuts.tsx` + `CommandPalette` + `KeyboardShortcutsModal` (expose/wire open handlers, add palette entry, add chord + modal list row), the Settings view (drop the Connect section), and route files under `settings/connect` + `settings/connected-apps` (redirect) with the page moved to `app/(authenticated)/connect/`.
- **No backend / MCP / API changes.** The Connect page content, `/api/config` `mcpServerUrl`, OAuth, and consent management are all unchanged — only placement and discoverability move.
- **Links/bookmarks preserved** via redirects; a "New" pill needs a small client-side dismissal signal (localStorage or first-connect check).
- **Tests**: nav item + chord, footer affordance click-opens-each-modal, palette "Keyboard shortcuts" entry, old-route redirects, Settings section removed.
- **Workflow**: spec-only; implementation via branch → PR → merge approval.
