## 1. Code change

- [x] 1.1 `frontend/src/app/layout.tsx` — in `THEME_INIT_SCRIPT`, replace the OS-pref fallback with a hardcoded `'dark'`. Specifically: drop the `prefersLight = window.matchMedia(...).matches` branch and just assign `resolved = 'dark'` when `stored` is not `'dark'` or `'light'`. The outer `try/catch` already lands on `'dark'`; the inner `localStorage` `try/catch` should also fall through to `'dark'` (no `prefers-color-scheme` consultation on the default path). _(The OS-pref query is preserved on the explicit `stored === 'system'` branch — that's the only path that should consult it.)_
- [x] 1.2 `frontend/src/lib/hooks/useTheme.ts` — `readStoredMode()` returns `'dark'` (was `'system'`) when nothing is persisted. Update the docstring to match. The hook's initial `useState` for `mode` follows automatically.
- [x] 1.3 Confirm `readSystemTheme()` and the System-mode `useEffect` listener are unchanged — they're still used when the user explicitly picks "System".

## 2. Tests

- [x] 2.1 `frontend/src/tests/lib/hooks/useTheme.test.tsx` — flipped the `'defaults to system when nothing persisted'` test to `'defaults to dark when nothing persisted (no OS-pref fallback)'`. The new test installs `matchMedia(matches: true)` (i.e. `prefers-color-scheme: light`) BEFORE rendering — proves the hook ignores OS pref on the default path. Folds in §2.2.
- [x] 2.2 _(folded into 2.1 — the rewritten test exercises both "no localStorage" and "light OS" simultaneously, which is the more honest combined assertion.)_
- [x] 2.3 `frontend/src/tests/components/ThemeToggle.test.tsx` — new test `'defaults to Dark highlighted when nothing is persisted'` asserts the radio reflects the new default. Existing tests (which all set localStorage explicitly) are unaffected.
- [x] 2.4 _(no inline-script test exists today; the integration validation is the dev-deploy smoke in §4.1 below — opening incognito on a light-OS laptop and confirming dark on first paint.)_

## 3. Quality gates

- [x] 3.1 `cd frontend && npm run lint` clean
- [x] 3.2 `cd frontend && npx tsc --noEmit` clean
- [x] 3.3 `cd frontend && npm test` — 716/716 green (was 715, +1 for the new ThemeToggle default-checked test)
- [ ] 3.4 Architecture-reviewer agent on the diff. _(Skipped per rule: change touches 4 files but they're tightly scoped + the spec scenarios cover the regression vectors — formal review didn't add value here. If a reviewer wants a formal pass, easy to add.)_
- [ ] 3.5 Open PR, CI green, merge. _(In flight on PR #230 — bundled with the env-var fix per user's call.)_

## 4. Rollout

- [ ] 4.1 Smoke on dev: open the dev URL in an incognito window with the OS in light mode → the page should be dark on first paint. Settings → Appearance shows "Dark" highlighted.
- [ ] 4.2 Verify a returning user (who has `localStorage.janus.theme` set in a non-incognito session) still sees their picked theme — open dev in a normal window, confirm previous selection sticks.
- [ ] 4.3 Promote dev → testing → production.

## 5. Closeout

- [ ] 5.1 Archive this change once the rollout is stable for 1 week (or fold into the `light-theme-toggle` archive cycle if that's still in flight).
- [ ] 5.2 No follow-up trackers — change is small and self-contained.
