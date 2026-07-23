## 1. Promote Connect to a top-level nav item

- [x] 1.1 Move the Connect page from `app/(authenticated)/settings/connect/` to `app/(authenticated)/connect/` (component unchanged); update `metadata` title if needed.
- [x] 1.2 Replace `settings/connect/page.tsx` with a redirect to `/connect`; keep `settings/connected-apps/page.tsx` redirecting to `/connect` (repoint from the old target).
- [x] 1.3 Add a `navItems` entry `{ href: '/connect', label: 'Connect AI' }` (not admin-only), placed near Settings.
- [x] 1.4 Remove the Settings ▸ Connect section from `SettingsView.tsx`.
- [x] 1.5 Add the `g i` → `/connect` chord to `NAV_CHORDS` in `GlobalShortcuts.tsx` and to the navigation list in `KeyboardShortcutsModal.tsx`.
- [x] 1.6 "New" pill on the nav item until first visit: set a `localStorage` flag (e.g. `sc0red-services.connect-seen`) when `/connect` renders; hide the pill once set.
- [x] 1.7 Tests: nav item present + routes to `/connect`; `g i` navigates; old routes redirect; Settings no longer shows a Connect section; pill shows then clears after visit.

## 2. Make shortcuts + palette discoverable

- [x] 2.1 Lift/expose the palette + shortcuts open handlers so both the key bindings (`GlobalShortcuts`) and a sidebar button can trigger them, WITHOUT changing the existing `Esc` precedence (palette > shortcuts) or the chord-suppression-while-open behavior. Prefer keeping `GlobalShortcuts` as state owner and sharing setters (small context/provider or hoist to layout).
- [x] 2.2 Extract a `SidebarFooter` sub-component (keeps `DashboardSidebar` under the 360-line limit) containing the user block + a muted, small, clickable affordance: `⌘K commands · ? shortcuts`, each a `<button>` opening its modal.
- [x] 2.3 Add a "Keyboard shortcuts" action to the command palette that opens the help modal (reusing the shared open handler).
- [x] 2.4 Tests: clicking the footer "commands" opens the palette; clicking "shortcuts" opens the help modal; the palette "Keyboard shortcuts" action opens the help modal; `Esc` precedence + chord suppression unchanged (regression).

## 3. Verify + ship

- [x] 3.1 `cd frontend && npm run lint && npx tsc --noEmit && npm test` — all green; components within size limits.
- [ ] 3.2 Manually verify on dev: "Connect AI" appears in the nav and opens the page; old `/settings/connect` + `/settings/connected-apps` redirect; footer affordance opens each modal on click; `g i` works; pill shows once then clears.
- [ ] 3.3 Branch → PR → E2E → merge approval (never commit to `development` directly).
