## ADDED Requirements

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
