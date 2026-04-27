## ADDED Requirements

### Requirement: Global navigation shortcuts via `g`-prefix chord

The webapp SHALL support `g`-prefix navigation chords on the authenticated app surface. After the user presses `g`, a subsequent key within 1 second navigates to the corresponding route. The chord SHALL only register when no input, textarea, or contenteditable element is focused.

| Chord | Destination |
|---|---|
| `g d` | `/dashboard` |
| `g a` | `/analyses` |
| `g s` | `/scan/new` |
| `g t` | `/team` |
| `g c` | `/settings` |

#### Scenario: User navigates to dashboard via chord

- **WHEN** the user is on `/analyses` (no focused input) and presses `g` then `d` within 1 second
- **THEN** the app navigates to `/dashboard`

#### Scenario: Chord resets after timeout

- **WHEN** the user presses `g`, then waits 2 seconds, then presses `d`
- **THEN** the chord buffer has reset; `d` alone does not navigate

#### Scenario: Chord ignored while typing in an input

- **WHEN** the user is focused in the analyses-page search input and types "good"
- **THEN** the literal text "good" appears in the input; no navigation occurs (the `g`-prefix shortcut does not fire)

### Requirement: `?` opens a keyboard shortcuts help modal

Pressing `?` (Shift+`/`) on the authenticated app surface, with no input focused, SHALL open a modal listing all available keyboard shortcuts grouped by category (Navigation, Search, Modal). The modal SHALL be dismissible via Esc or backdrop click.

#### Scenario: User opens help modal

- **WHEN** the user presses `?` on `/dashboard`
- **THEN** a modal renders with sections for Navigation (`g d`, `g a`, etc.), Search (`Cmd+K`, `/`), and Modal (`Esc` to close)

#### Scenario: Modal dismisses on Esc

- **WHEN** the help modal is open and the user presses Esc
- **THEN** the modal closes

### Requirement: `Esc` closes any open modal or dialog

Pressing `Esc` SHALL close the topmost open modal or dialog (command palette, confirm dialog, shortcuts help modal). If multiple modals are open, the topmost closes first; only one Esc press is consumed per modal.

#### Scenario: Esc closes the command palette

- **WHEN** Cmd+K is pressed (palette opens) and Esc is pressed
- **THEN** the palette closes

#### Scenario: Esc with no modal open does nothing

- **WHEN** the user is on `/dashboard` with no modal open and presses Esc
- **THEN** no behavior change; default browser behavior is preserved

### Requirement: `/` focuses search on pages with a search field

On pages with a primary search field (currently `/analyses`), pressing `/` with no input focused SHALL move focus to that search field and prevent the default character entry.

#### Scenario: User focuses search via slash

- **WHEN** the user is on `/analyses` (no focused input) and presses `/`
- **THEN** focus moves to the AnalysesToolbar search input; the `/` character does not appear in the input

#### Scenario: Slash on page without search does nothing

- **WHEN** the user is on `/dashboard` (no search field) and presses `/`
- **THEN** no behavior change
