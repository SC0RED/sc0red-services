## Context

`globals.css` is 1620 lines, single-`:root`. Every component that needs a color either reads `var(--token)` (already correct, will switch values automatically) or has a hardcoded hex string in `style={{...}}` (needs migration). Recharts uses constants from `lib/utils/riskUtils.ts` and `lib/utils/leverColors.ts` — those resolve to hex strings at module load and don't track the theme.

Two surfaces stress the design:

1. **Initial paint without flash-of-wrong-theme.** React hydration runs after the browser paints once. If the theme is set in a `useEffect`, the user sees ~100ms of "wrong" theme before it corrects. The standard fix is a synchronous inline script in `<head>` that runs before any CSS resolves.
2. **Charts.** Recharts evaluates color props at render time. If we hand it a CSS variable (`fill="var(--accent-blue)"`), recent versions handle that fine in modern browsers. But the existing code hands it hex strings. Migration: either change the props to vars (works today in Chrome/Safari/Firefox), or wrap chart components in a hook that resolves vars to hex strings on the client.

## Goals / Non-Goals

**Goals:**
- Two complete palettes (dark + light) sharing the same variable names.
- User-selectable mode: Dark / Light / System.
- Persisted to `localStorage`, applied before first paint.
- `@media print` forces light, regardless of user choice.
- Charts (Recharts) follow the active theme correctly.
- Single source of truth — no duplicate stylesheets, no theme-specific component variants.

**Non-Goals:**
- Cross-device sync (localStorage only).
- Time-of-day auto-switching.
- Multi-tenant brand themes.
- Custom user-defined palettes (high-contrast, AAA, etc.).
- Mobile-specific theme adjustments — separate Tier 3 scope.

## Decisions

### D1. Single stylesheet, dual `:root` via attribute selector

**Decision:** keep `globals.css` as the single stylesheet. Add a second `:root` block scoped to `[data-theme="light"]` that overrides the dark values:

```css
:root {
    --bg-base: #060a12;
    --text-primary: #eef2ff;
    /* ... 70+ tokens ... */
}

[data-theme="light"] :root,
:root[data-theme="light"] {
    --bg-base: #ffffff;
    --text-primary: #0a0e1a;
    /* ... 70+ tokens ... */
}
```

**Why one stylesheet, not two:** simpler. No `<link rel="stylesheet">` swap, no FOUC during stylesheet load, no double-download. CSS variable cascade handles everything.

**Why `[data-theme]` attribute, not a class:** attributes carry stronger semantic intent ("this element IS the light theme") and integrate cleanly with `@media (prefers-color-scheme: light)` in CSS-only fallback paths.

### D2. Initial-paint script: synchronous inline `<script>` in `<head>`

**Decision:** `app/layout.tsx` injects an inline script before any React renders:

```tsx
<head>
  <Script
    id="theme-init"
    strategy="beforeInteractive"
    dangerouslySetInnerHTML={{
      __html: `
        (function() {
          try {
            var stored = localStorage.getItem('janus.theme');
            var pref = stored === 'light' || stored === 'dark'
              ? stored
              : (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
            document.documentElement.setAttribute('data-theme', pref);
          } catch (e) {}
        })();
      `,
    }}
  />
</head>
```

**Why inline, not a module import:** must run synchronously before the first CSS rule applies. Module imports are async; React effects fire post-paint.

**Why fallback to dark on `localStorage` access failure:** Safari private mode throws on `localStorage.getItem`. Defensive `try/catch` falls through to OS pref, then to dark. No crash, no white-flash for users with disabled storage.

### D3. Three-option toggle: Dark / Light / System

**Decision:** Settings → Appearance section has a radio group with three options. `System` stores the literal string `"system"` in `localStorage` and re-resolves on every page load via `prefers-color-scheme`.

**Why three options not two:** "follow my OS" is the modern default. Users who switch their OS theme during the day (light during work, dark at night) want the app to follow.

**Why radio buttons not a switch:** a switch implies binary; three states need a tri-state UI, which is non-standard. Three radio buttons match the user's mental model.

### D4. `@media print` overrides regardless of user choice

**Decision:** `@media print` block in `globals.css` re-declares all light-theme variables on `:root`:

```css
@media print {
    :root {
        --bg-base: #ffffff;
        --text-primary: #0a0e1a;
        /* ... matches [data-theme="light"] :root ... */
    }
}
```

**Why duplicate the block instead of `@media print { html { /* re-attribute */ } }`:** more reliable across browsers. CSS attribute selectors interact with `@media` inconsistently in Firefox + older WebKit. Re-declaring tokens is the cross-browser-safe path.

**Maintenance trade-off:** the light-theme tokens now appear in two places — `[data-theme="light"]` and `@media print`. A future "add a new color token" needs to update both. Mitigation: a comment in `globals.css` flags the duplication; a CI lint rule could pick up the gap (deferred to a follow-up).

### D5. Charts: CSS-variable-driven via a `useThemedColor` hook

**Decision:** Recharts color constants in `riskUtils.ts` / `leverColors.ts` move to CSS variable names (e.g., `--risk-critical`, `--lever-revenue`). A new `useThemedColor(token)` hook reads `getComputedStyle(document.documentElement).getPropertyValue('--risk-critical')` and returns the resolved hex.

**Why a hook, not raw `var(...)` in chart props:** Recharts in some chart types (custom shapes, dynamic fill calculations) reads the prop value programmatically and does color math on it. CSS variables don't survive that. A hook gives us a real string at render time.

**Why useThemedColor and not a global theme context:** the cost of `getComputedStyle` is negligible at chart render frequency. A context would force every chart to subscribe to theme changes; the hook is opt-in per chart and re-runs on theme change via a `useEffect` listening for the custom `theme-change` event the toggle dispatches.

**SSR consideration:** during server-side render the document doesn't exist. The hook returns the dark-theme default (matches the inline-script-set `data-theme`); the client re-renders with the actual value after hydration. For analyses pages this is fine — the chart is below-the-fold and re-renders are cheap.

### D6. Localstorage key, not session storage; no backend persistence

**Decision:** `localStorage.setItem('janus.theme', value)` only. No backend write.

**Why no backend:** cross-device sync is a nice-to-have, not a must-have. A user who logs in on a different machine and gets the OS default is fine — they can re-toggle once, and their per-device preference sticks. Backend persistence adds a write-on-toggle round-trip, schema complexity (per-user-preference table), and a sync conflict story. Not worth it for a UI preference at this scale.

**Why `localStorage` not `sessionStorage`:** preference should survive logout/login and tab close. Session storage clears on tab close.

## Risks

| Risk | Mitigation |
|---|---|
| **FOUC (flash of unstyled content)** during initial paint | Inline `<script>` in `<head>` runs before CSS evaluates. Standard pattern; works in every modern browser. |
| **Inline-style hex strings still bypass theme** | Component audit catches them. Linting rule (deferred): `eslint-plugin-tailwindcss`-style check or a custom rule that flags inline-style `background:`/`color:` with hex values. |
| **Recharts colors don't track theme** | `useThemedColor` hook + custom `theme-change` event the toggle dispatches. Charts re-render with new colors. |
| **WCAG AA contrast violations in light theme** | Run axe-core in dev; manual contrast check on every page in both themes during apply. Adjust light-theme tokens until 4.5:1 / 3:1 thresholds met. |
| **`@media print` and `[data-theme]` interact in some browsers** | D4 explicitly re-declares the tokens in `@media print`. Tested across Chrome / Safari / Firefox during apply. |
| **`localStorage` unavailable** (Safari private mode) | Inline script's `try/catch` falls through to OS pref. Toggle silently fails to persist (selection lasts the session) — degraded but not broken. |
| **Hydration mismatch warnings** | The `data-theme` attribute is set on `<html>` BEFORE React hydrates, so the server-rendered HTML and the client-side JS agree. No mismatch. |

## Open Questions

1. **Recharts approach — CSS-var-in-prop vs `useThemedColor`?** D5 leans hook. Validate at apply time by trying CSS-var-in-prop on one chart; if Recharts handles it cleanly across all chart types we use, drop the hook for simpler code.
2. **Visual-regression test infra**: do we want Percy / Chromatic / Playwright screenshots locked in for the dark+light combinations? Current frontend tests are vitest-only. Decision: defer to follow-up; manual smoke during apply is sufficient for v1.
3. **Light-theme palette specifics**: design exercise during apply. The dark-theme accent blue (`#3B7BF6`) is too saturated for white backgrounds — needs a slightly desaturated counterpart (`#2563eb` or similar). Same for accent-cyan, accent-red, etc. The full palette swap is the bulk of the visual design work.
