## Context

`light-theme-toggle` shipped a Dark / Light / System toggle persisted to `localStorage.janus.theme`. The bootstrap script in `app/layout.tsx` runs synchronously in `<head>` to set `<html data-theme>` before React hydrates. When no `localStorage.janus.theme` is present (new visitor, cleared storage, Safari private mode), the script falls through to `window.matchMedia('(prefers-color-scheme: light)')` and resolves `light` or `dark` based on OS preference.

The product is dark-first by design: the marketing site, screenshots, sales decks, and Loom recordings are all dark. A first-time visitor on a light-mode laptop (the macOS default) lands on a *light* webapp, immediately disconnected from the brand. The fix is a one-line fallback flip — but the spec consequences (which scenarios are guaranteed, which are explicitly NOT) are worth pinning down.

The `useTheme()` hook independently defaults to `mode = "system"` for users with no persisted choice. That has to flip in lockstep with the bootstrap script — otherwise the Settings → Appearance radio shows "System" selected even though the page is showing dark, which would be confusing.

## Goals / Non-Goals

**Goals:**
- New users (and any user who clears `localStorage.janus.theme`) land on **dark** regardless of OS preference.
- Settings → Appearance highlights "Dark" on first visit, matching the rendered theme.
- Existing users with any persisted choice (`dark`, `light`, `system`) see **zero** behavioural change.
- The "System" mode remains available and continues to follow OS pref live when the user explicitly opts in.
- The flash-of-wrong-theme guarantee from `light-theme-toggle` is preserved.

**Non-Goals:**
- Removing the System option from the Settings UI (it's a power-user affordance, kept).
- Removing the `prefers-color-scheme` query from the codebase (still used by the System-mode active branch and the live OS-change listener).
- Server-side persistence of the theme preference (out of scope, tracked separately).
- Changing any token values, the `@media print` block, or the chart-color re-resolution path.
- Migrating existing users — no need; the change only affects the cold-start fallback.

## Decisions

### D1. Bootstrap script: drop OS-pref fallback, hardcode `'dark'`

**Decision:** in `THEME_INIT_SCRIPT`, when `localStorage.getItem('janus.theme')` is `null`/missing/throws, set `data-theme` to `'dark'` directly.

**Why hardcode rather than continue resolving OS pref:**
- The OS-pref fallback was inherited from a generic theme-toggle pattern; it's not the product's stated default. Pinning to `dark` makes the brand promise consistent with the first paint.
- Removing the fallback simplifies the script: one branch (stored value) vs. two (stored value + OS resolution). Less to drift on.
- The OS-pref query is still preserved on the *active* path: when a user explicitly picks "System" mode, `useTheme()`'s `useEffect` listens for `prefers-color-scheme` changes and re-resolves. The query isn't dead code — it's just not the *default* path anymore.

**Trade-off:** users on dark-mode OS who previously got dark-by-OS-pref now get dark-by-default. Same outcome. Users on light-mode OS who previously got light-by-OS-pref now get dark-by-default. **This is the intentional change**; the new default surfaces the System option to users who actually want OS-followed behaviour by giving them a clean place to opt in (Settings).

### D2. `useTheme()` initial state defaults to `"dark"`, not `"system"`

**Decision:** `readStoredMode()` returns `"dark"` when `localStorage.janus.theme` is absent or unreadable. The hook's initial `mode` state therefore starts at `"dark"`.

**Why this matters:** if the bootstrap script flipped but the hook didn't, a new user would see dark on the page (correct) but the Settings → Appearance radio would have "System" highlighted (wrong). Two sources of truth, instant confusion. Both flip together.

**Why `"dark"` not `"light"`:** the Settings UI now reflects what's actually rendered. A user who hits Settings on first visit sees Dark selected, matching what they see on the page.

### D3. Existing users untouched

**Decision:** any value in `localStorage.janus.theme` (`"dark"`, `"light"`, `"system"`, or even malformed strings that the script's existing validation rejects) keeps current behaviour.

**Why:** the people most likely to notice a change are the people who already chose a setting. Touching their preference would be a regression. The scenario "I picked Light yesterday and today the app is suddenly Dark" must NOT happen.

**Verification:** the spec scenarios explicitly cover the three persisted cases (`dark`, `light`, `system`) to prevent a future refactor from accidentally catching them in the default-flip net.

### D4. Safari private mode falls through to dark, not OS pref

**Decision:** when `localStorage.getItem` throws (Safari private mode is the canonical case), the inner `try/catch` lands on the same `'dark'` default as the no-storage case.

**Why simplify:** the prior behaviour fell through to `prefers-color-scheme`. With the new policy, we just fall through to dark — same as the no-storage path. Removes a special case.

**Risk:** users in Safari private mode who picked Light on their main browser session won't carry that across — but they don't carry localStorage either, so this isn't a regression specific to the change. They get the same "no preference" behaviour as a brand-new visitor.

### D5. Capability is "Modified", not "New"

**Decision:** this is a delta on `light-theme-toggle`, not a new capability. The delta spec ADDs an explicit "default mode" requirement to clarify the previously-implicit behaviour.

**Why ADD rather than MODIFY:** the existing requirement ("User-selectable theme with three modes") doesn't say anything explicit about the default — it talks about what happens when the user *selects* a mode. The default-mode behaviour was implicit in the bootstrap script and the hook's `useState` initial value. Making it explicit via an ADDED requirement is cleaner than retroactively patching the existing requirement to say what it never said.

When the `light-theme-toggle` change archives (after its 1-week stable window), the sync will pick up both — the original three-mode-toggle requirement plus this default-dark requirement. They're complementary, not in conflict.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| User on a light-mode OS sees dark on first visit and thinks the app "doesn't follow my OS" — can't find the System option | Settings → Appearance is one click from the avatar menu. The System option is right there. Acceptable friction for the brand-consistency win. |
| A future refactor accidentally drops the explicit-default requirement from the spec | Architecture-reviewer + the new scenarios in the delta spec. The "existing user with `system` persisted" scenario locks the boundary. |
| Tests that asserted on `mode === 'system'` for new users break | Two known sites (`useTheme.test.tsx`, `ThemeToggle.test.tsx`); flagged in tasks.md. |
| Regression on the "no flash of wrong theme" guarantee | The bootstrap script still runs synchronously in `<head>`. Fewer branches than before — strictly less surface to flash. |
| Marketing or product asks for "follow OS" later as the default | The toggle is already there. We can flip the fallback back. The decision is reversible with a one-line change. |

## Migration Plan

1. Land the code change on `development` (one PR, ~four files modified).
2. Dev deploy → smoke (open in incognito → confirm dark on first paint regardless of OS).
3. Promote to testing → repeat smoke.
4. Promote to production. No backend migration, no DB change, no Secrets Manager involvement.
5. Roll back via revert if needed (single commit; no schema or data dependencies).

**Rollback criterion:** if the brand-consistency win turns out to be invisible *and* a meaningful number of users complain that the app doesn't follow their OS, revert. Bar is low; the change is small.

## Open Questions

1. **Should we add a one-time toast on first visit explaining the toggle exists?** Probably not — it would be discoverability cruft that 99% of users don't need. The Settings page is the right home for the explanation.
2. **Should `useTheme()` expose a way to distinguish "user hasn't chosen" from "user picked dark"?** Today both are stored as the same effective state once the user opens Settings (the radio defaults to Dark, so first interaction may persist `"dark"` even if the user is just exploring). Not a blocker — `localStorage` after first interaction is fine — but worth a tracker if anyone needs to count "implicitly defaulted" vs. "explicitly chose dark."
3. **Should we backfill existing `localStorage.janus.theme: "system"` users to `"dark"`?** Explicitly NO — that's the regression vector D3 protects against. Stays open here only to flag that the answer is no.
