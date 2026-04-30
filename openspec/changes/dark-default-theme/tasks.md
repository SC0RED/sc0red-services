## 1. Code change

- [ ] 1.1 `frontend/src/app/layout.tsx` — in `THEME_INIT_SCRIPT`, replace the OS-pref fallback with a hardcoded `'dark'`. Specifically: drop the `prefersLight = window.matchMedia(...).matches` branch and just assign `resolved = 'dark'` when `stored` is not `'dark'` or `'light'`. The outer `try/catch` already lands on `'dark'`; the inner `localStorage` `try/catch` should also fall through to `'dark'` (no `prefers-color-scheme` consultation on the default path).
- [ ] 1.2 `frontend/src/lib/hooks/useTheme.ts` — `readStoredMode()` returns `'dark'` (was `'system'`) when nothing is persisted. Update the docstring to match. The hook's initial `useState` for `mode` follows automatically.
- [ ] 1.3 Confirm `readSystemTheme()` and the System-mode `useEffect` listener are unchanged — they're still used when the user explicitly picks "System".

## 2. Tests

- [ ] 2.1 `frontend/src/tests/lib/hooks/useTheme.test.tsx` — flip the `'defaults to system when nothing persisted'` test to `'defaults to dark when nothing persisted'`. Assert `result.current.mode === 'dark'`. Keep the explicit `system` test path (when `localStorage` has `'system'`).
- [ ] 2.2 Add a test: `'no localStorage + light OS still defaults to dark'`. Use the `installMatchMedia(true)` helper to fake light-OS pref; assert the hook's `mode` is `'dark'` and `resolved` is `'dark'`.
- [ ] 2.3 `frontend/src/tests/components/ThemeToggle.test.tsx` — the test that currently expects `mode === 'system'` after rendering with no persisted preference should be updated to expect `'dark'`. The "System click writes 'system' to localStorage" test stays as-is.
- [ ] 2.4 Smoke that the bootstrap script's behaviour matches: `frontend/src/tests/app/layout.test.tsx` (or wherever the bootstrap script is exercised). If no test exists today for the inline script, this change doesn't add one — the integration test of "open in incognito → see dark" lives in §3 below.

## 3. Quality gates

- [ ] 3.1 `cd frontend && npm run lint` clean
- [ ] 3.2 `cd frontend && npx tsc --noEmit` clean
- [ ] 3.3 `cd frontend && npm test` — all green; the two updated tests + one new test should land.
- [ ] 3.4 Architecture-reviewer agent on the diff (touches 2 source files + 2 test files — under the 3-file threshold but the change has spec consequences; safe to skip if you prefer).
- [ ] 3.5 Open PR, CI green, merge.

## 4. Rollout

- [ ] 4.1 Smoke on dev: open the dev URL in an incognito window with the OS in light mode → the page should be dark on first paint. Settings → Appearance shows "Dark" highlighted.
- [ ] 4.2 Verify a returning user (who has `localStorage.janus.theme` set in a non-incognito session) still sees their picked theme — open dev in a normal window, confirm previous selection sticks.
- [ ] 4.3 Promote dev → testing → production.

## 5. Closeout

- [ ] 5.1 Archive this change once the rollout is stable for 1 week (or fold into the `light-theme-toggle` archive cycle if that's still in flight).
- [ ] 5.2 No follow-up trackers — change is small and self-contained.
