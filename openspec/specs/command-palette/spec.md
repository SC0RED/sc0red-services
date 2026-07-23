# command-palette Specification

## Purpose
TBD - created by archiving change webapp-ux-foundations-tier1. Update Purpose after archive.
## Requirements
### Requirement: Cmd-K opens a global command palette

While the user is in the authenticated app surface, pressing `Cmd+K` (macOS) or `Ctrl+K` (Windows/Linux) SHALL open a fuzzy-search command palette overlaid on the current page. The palette SHALL NOT render on unauthenticated routes (`/login`, `/forgot-password`, `/accept-invite`, `/oauth/*`).

#### Scenario: Authenticated user opens palette

- **WHEN** the user is on `/dashboard` and presses Cmd+K
- **THEN** a modal palette renders centered (or top-third of viewport), with a search input focused, listing default suggestions

#### Scenario: Unauthenticated user sees no palette

- **WHEN** the user is on `/login` and presses Cmd+K
- **THEN** nothing happens — no palette renders, default browser behavior is preserved

#### Scenario: Palette dismisses on Esc

- **WHEN** the palette is open and the user presses Esc
- **THEN** the palette closes; focus returns to the previously-focused element

#### Scenario: Palette dismisses on backdrop click

- **WHEN** the palette is open and the user clicks outside the palette body
- **THEN** the palette closes

### Requirement: Palette searches over companies, portfolios, and actions

The command palette SHALL provide three categories of results:

1. **Companies** — by name, drawn from the user's existing analyses (last loaded list; no fresh fetch). Selecting navigates to `/analysis/{id}`.
2. **Portfolios** — by scan name, drawn from recent scans of type `portfolio`. Selecting navigates to `/portfolio/{scanId}`.
3. **Actions** — top-level actions (`New Scan`, `View Team`, `View Settings`, `View Dashboard`, `View Analyses`). Selecting performs the action (typically navigation).

Categories SHALL be visually grouped with a heading. Empty input SHALL show all default actions and the most-recent companies/portfolios.

#### Scenario: Typing fuzzy-matches across categories

- **WHEN** the user types "acm" and the analyses list contains "Acme Corp"
- **THEN** "Acme Corp" appears under the Companies group

#### Scenario: Action selection navigates

- **WHEN** the user types "scan", arrows down to "New Scan", and presses Enter
- **THEN** the palette closes and the user navigates to `/scan/new`

#### Scenario: Empty query shows defaults

- **WHEN** the user opens the palette and types nothing
- **THEN** all available actions render under their group, plus up to 5 most-recent companies and portfolios under their respective groups

### Requirement: Palette is accessible

The command palette SHALL be operable via keyboard alone. Arrow keys navigate results, Enter selects, Esc closes. The active item SHALL have visible focus styling. The palette SHALL trap focus while open and return focus to the trigger element on close.

#### Scenario: Arrow keys navigate results

- **WHEN** the palette is open with multiple results
- **THEN** ArrowDown highlights the next item, ArrowUp the previous; the highlighted item is visually distinct

#### Scenario: Focus is trapped while open

- **WHEN** the palette is open and the user presses Tab
- **THEN** focus stays within the palette body (input + interactive results) — does not leak to elements behind the modal

#### Scenario: Focus returns on close

- **WHEN** the user opens the palette via Cmd+K from a button, then presses Esc
- **THEN** focus returns to the button that originally triggered the open

### Requirement: The command palette is discoverable and can open the shortcuts help

The command palette SHALL be discoverable by a user who does not already know the `⌘K` / `Ctrl-K` shortcut. The authenticated sidebar SHALL show a persistent, unobtrusive (muted, small) affordance that opens the command palette on click. The palette SHALL also include a "Keyboard shortcuts" action that opens the keyboard-shortcuts help modal, so palette users can find the full shortcut list.

#### Scenario: A mouse user opens the palette from the sidebar

- **WHEN** the user clicks the "commands" affordance in the sidebar footer
- **THEN** the command palette opens (the same palette `⌘K` / `Ctrl-K` opens)

#### Scenario: The palette can open the shortcuts help

- **WHEN** the user opens the command palette and selects the "Keyboard shortcuts" action
- **THEN** the keyboard-shortcuts help modal opens

