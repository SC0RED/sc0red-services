## Why

The recently-shipped `light-theme-toggle` change introduced three modes (Dark / Light / System), and made **System** the implicit default for users with no persisted preference — meaning new users on macOS / Windows / GNOME with light-mode OS preferences land on a *light* webapp on first visit. The product's visual identity, marketing, and screenshots are all dark-themed; the SaaS table-stakes "looks correct on first paint" is broken for the majority of new visitors. This change makes Dark the default for users with no stored preference, while keeping the existing three-option toggle (so users who explicitly want System or Light can still pick those).

## What Changes

- The bootstrap script in `app/layout.tsx` no longer falls back to `prefers-color-scheme` when `localStorage.janus.theme` is absent — it sets `data-theme="dark"` directly. Existing users with a stored preference (`dark`, `light`, or `system`) are unaffected; only new users / cleared-storage users see the change.
- `useTheme()` hook's initial-render `mode` defaults to `"dark"` (was `"system"`) when nothing is persisted. Concretely: the Settings → Appearance radio group highlights "Dark" on first visit, not "System".
- Settings → Appearance still lists all three options (Dark / Light / System) — users who want OS-followed behaviour can opt in explicitly. The `prefers-color-scheme` query is preserved and still drives the resolved theme when the user picks "System".
- The "no preference + Safari private mode" path (where `localStorage.getItem` throws) now lands on dark instead of OS-pref dark. Same outcome on dark-OS users; lighter regression surface for light-OS users in private mode.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `light-theme-toggle`: the "User-selectable theme with three modes" requirement currently leaves the default for new users implicit (resolved against `prefers-color-scheme`). We add an explicit requirement that the default is `"dark"`. Three new scenarios cover: (a) new user, light OS → still gets dark; (b) new user, dark OS → gets dark; (c) existing user with stored "system" → unchanged.

## Impact

**Modified**:
- `frontend/src/app/layout.tsx` — bootstrap script `THEME_INIT_SCRIPT` falls back to `'dark'` instead of `prefers-color-scheme` resolution.
- `frontend/src/lib/hooks/useTheme.ts` — `readStoredMode()` returns `'dark'` (was `'system'`) when nothing is persisted; `useTheme()` initial state follows.
- `frontend/src/tests/lib/hooks/useTheme.test.tsx` — the `'defaults to system when nothing persisted'` test flips to `'defaults to dark when nothing persisted'`.
- `frontend/src/tests/components/ThemeToggle.test.tsx` — the radio default-selection test updates accordingly.

**Unaffected**:
- `globals.css` palette tokens (still dual; light path stays correct for users who pick Light).
- `@media print` light forcing (still correct — Cmd+P on a dark-default screen still prints light).
- Existing users with `localStorage.janus.theme` set (any value): zero behavioural change.
- The `useTheme().resolved` for `mode === 'system'` users still tracks the OS preference live.

**Not in scope**:
- Removing the System option from the toggle (kept — it's a power-user affordance).
- Removing the `prefers-color-scheme` query from the bootstrap script (kept for the System-mode active branch).
- Server-side persistence of the preference (still localStorage-only — out of scope, tracked in light-theme-toggle's follow-ups).
- Reverting any of the dark-mode or print-mode token decisions from `light-theme-toggle`.

**Migration**:
- No migration. Existing users keep whatever preference they have. The change only affects the cold-start no-localStorage path.

**Risk**:
- Low. The change is a one-line fallback flip in two places (bootstrap + hook) plus two test updates. The architecturally-significant decisions (dual palette, single token namespace, custom event for chart re-resolution) all stay intact.
