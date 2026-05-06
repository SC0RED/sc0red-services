# light-theme-toggle Specification

## Purpose

User-selectable theme system with three modes (Dark, Light, System), single-token dual-palette CSS architecture, print-forced light theme, and theme-aware charts.

## Requirements

### Requirement: User-selectable theme with three modes

The application SHALL expose a Settings → Appearance section with three theme modes: `Dark`, `Light`, and `System` (follow OS `prefers-color-scheme`). The selection SHALL be persisted to `localStorage` under the key `janus.theme`. On every page load the persisted choice (or, if `"system"`, the current OS preference) SHALL be applied to the `<html>` element via a `data-theme` attribute BEFORE React hydrates, so the user never sees a flash-of-wrong-theme.

#### Scenario: User selects light mode

- **WHEN** the user picks "Light" in Settings → Appearance
- **THEN** `localStorage.janus.theme` is set to `"light"`, `<html data-theme>` becomes `"light"`, and the page repaints with light-theme tokens

#### Scenario: User selects system mode and OS is light

- **WHEN** the user picks "System" in Settings → Appearance
- **AND** the OS reports `prefers-color-scheme: light`
- **THEN** `localStorage.janus.theme` is set to `"system"`, and `<html data-theme>` is `"light"` for the current load

#### Scenario: User reloads the page after selecting light

- **WHEN** the user has previously selected "Light"
- **AND** the page is reloaded
- **THEN** the inline `<head>` script reads `localStorage` and sets `data-theme="light"` before any CSS resolves; no flash of dark theme is visible

#### Scenario: localStorage is unavailable (Safari private mode)

- **WHEN** `localStorage.getItem` throws an exception
- **THEN** the inline script falls through to `prefers-color-scheme` for the current load
- **AND** the toggle in Settings still updates the in-memory theme (the change just doesn't persist across reloads)

### Requirement: Single token system, dual palette

`globals.css` SHALL use a single set of CSS variable names (e.g., `--bg-base`, `--text-primary`, `--accent-blue`) declared on `:root`. Light-theme values are declared on `[data-theme="light"] :root` (and equivalently `:root[data-theme="light"]`), overriding the dark-theme defaults. Components SHALL consume colors via `var(--token)` rather than hardcoded hex strings, so a single `data-theme` flip changes every color in the document.

#### Scenario: A component references --bg-base

- **WHEN** a component's CSS or inline-style uses `var(--bg-base)`
- **AND** the user switches from dark to light theme
- **THEN** the rendered background color updates from `#060a12` to the light-theme value (`#ffffff` or similar) without any component re-render

#### Scenario: A new color is needed and no existing token fits

- **WHEN** a new design need surfaces a color not in the current token list
- **THEN** the new variable MUST be declared in BOTH the dark `:root` and the `[data-theme="light"] :root` blocks (and the `@media print` block)
- **AND** components reference the variable, never the raw hex

### Requirement: Print output forces light theme

The application SHALL force the light theme during printing regardless of the user's screen preference. A `@media print` block in `globals.css` SHALL re-declare the light-theme variables directly on `:root` so any `Cmd+P` from any page renders light-on-white.

#### Scenario: User prints from the analysis detail page in dark mode

- **WHEN** the user has dark mode selected on screen
- **AND** opens the browser print preview from `/analysis/{id}`
- **THEN** the print preview shows light-theme colors (white background, dark text), NOT the dark-mode rendering

#### Scenario: Print stylesheet hides non-content chrome

- **WHEN** the user opens print preview on any page with the dashboard sidebar visible
- **THEN** the sidebar is hidden in the print preview
- **AND** the main content uses the full page width

### Requirement: Charts honor the active theme

Recharts colors that today come from hardcoded hex constants in `lib/utils/riskUtils.ts` and `lib/utils/leverColors.ts` SHALL resolve dynamically based on the active theme. A `useThemedColor(tokenName)` hook reads `getComputedStyle(document.documentElement).getPropertyValue(tokenName)` and returns the resolved hex string. Charts subscribe to a `janus:theme-change` custom event so they re-render with new colors on toggle.

#### Scenario: Risk score chart in dark mode

- **WHEN** the user is in dark mode on an analysis detail page
- **THEN** risk-tier-colored bars use the dark-theme accent values (saturated for dark backgrounds)

#### Scenario: User toggles to light, charts update

- **WHEN** a chart is rendered on screen in dark mode
- **AND** the user switches to light mode via Settings
- **THEN** the chart re-renders with light-theme color values within the same React update cycle, no manual reload required

### Requirement: Default theme is dark for users with no persisted preference

When `localStorage.janus.theme` is absent, unreadable, or holds a value not in the set `{"dark", "light", "system"}`, the application SHALL apply `data-theme="dark"` on the `<html>` element AND initialise `useTheme().mode` to `"dark"`. The bootstrap script SHALL NOT consult `prefers-color-scheme` to derive this default. The OS-preference query MAY still be referenced by the runtime when the user has explicitly selected `"system"` mode (per the existing "User-selectable theme with three modes" requirement) — only the *default* path is affected.

This requirement does NOT change behaviour for any user who has a stored preference of `"dark"`, `"light"`, or `"system"`. The change applies strictly to the cold-start no-preference path.

#### Scenario: New visitor on a light-OS laptop sees dark on first paint

- **WHEN** a brand-new visitor (no `localStorage.janus.theme` present) loads the application
- **AND** their OS reports `prefers-color-scheme: light`
- **THEN** the bootstrap script writes `data-theme="dark"` to `<html>` before React hydrates
- **AND** Settings → Appearance shows the "Dark" radio selected

#### Scenario: New visitor on a dark-OS laptop sees dark on first paint

- **WHEN** a brand-new visitor (no `localStorage.janus.theme` present) loads the application
- **AND** their OS reports `prefers-color-scheme: dark`
- **THEN** the bootstrap script writes `data-theme="dark"` to `<html>` before React hydrates
- **AND** Settings → Appearance shows the "Dark" radio selected

#### Scenario: Returning user who previously selected "System" is unaffected

- **WHEN** a returning user with `localStorage.janus.theme` set to `"system"` loads the application
- **AND** their OS reports `prefers-color-scheme: light`
- **THEN** the bootstrap script writes `data-theme="light"` (system mode resolves OS pref live, per the existing requirement)
- **AND** Settings → Appearance shows the "System" radio selected — NO regression to "Dark"

#### Scenario: Returning user who previously selected "Light" is unaffected

- **WHEN** a returning user with `localStorage.janus.theme` set to `"light"` loads the application
- **THEN** the bootstrap script writes `data-theme="light"` to `<html>`
- **AND** Settings → Appearance shows the "Light" radio selected — NO regression to "Dark"

#### Scenario: Returning user who previously selected "Dark" is unaffected

- **WHEN** a returning user with `localStorage.janus.theme` set to `"dark"` loads the application
- **THEN** the bootstrap script writes `data-theme="dark"` to `<html>`
- **AND** Settings → Appearance shows the "Dark" radio selected (no observable change vs. prior behaviour)

#### Scenario: Safari private mode with no persisted preference

- **WHEN** the user is in Safari private mode (where `localStorage.getItem` throws)
- **THEN** the inner `try/catch` falls through to `data-theme="dark"`
- **AND** the OS `prefers-color-scheme` is NOT consulted for the default
- **AND** the in-memory `useTheme().mode` is `"dark"`; the user can still switch to Light or System for the current session, but the change won't persist
