## MODIFIED Requirements

### Requirement: Global navigation shortcuts via `g`-prefix chord

The webapp SHALL support `g`-prefix navigation chords on the authenticated app surface. After the user presses `g`, a subsequent key within 1 second navigates to the corresponding route. The chord SHALL only register when no input, textarea, or contenteditable element is focused.

| Chord | Destination |
|---|---|
| `g d` | `/dashboard` |
| `g a` | `/analyses` |
| `g s` | `/scan/new` |
| `g t` | `/team` |
| `g c` | `/settings` |
| `g i` | `/connect` |

#### Scenario: User navigates to dashboard via chord

- **WHEN** the user is on `/analyses` (no focused input) and presses `g` then `d` within 1 second
- **THEN** the app navigates to `/dashboard`

#### Scenario: User navigates to Connect via chord

- **WHEN** the user (no focused input) presses `g` then `i` within 1 second
- **THEN** the app navigates to `/connect`

#### Scenario: Chord resets after timeout

- **WHEN** the user presses `g`, then waits 2 seconds, then presses `d`
- **THEN** the chord buffer has reset; `d` alone does not navigate

#### Scenario: Chord ignored while typing in an input

- **WHEN** the user is focused in the analyses-page search input and types "good"
- **THEN** the literal text "good" appears in the input; no navigation occurs (the `g`-prefix shortcut does not fire)

## ADDED Requirements

### Requirement: Keyboard shortcuts are discoverable without prior knowledge

The shortcuts help SHALL be discoverable by a user who does not already know the `?` shortcut, and by mouse-only users. The authenticated sidebar SHALL show a persistent, unobtrusive (muted, small) affordance that opens the keyboard-shortcuts help modal on click — not merely a text hint to "press ?". The shortcuts help modal SHALL list the Connect navigation chord alongside the other `g`-chords.

#### Scenario: A mouse user opens the shortcuts help from the sidebar

- **WHEN** the user clicks the "shortcuts" affordance in the sidebar footer
- **THEN** the keyboard-shortcuts help modal opens (the same modal the `?` key opens)

#### Scenario: The Connect chord is listed in the help

- **WHEN** the shortcuts help modal is open
- **THEN** it lists the Connect navigation chord (`g i` → Connect) among the navigation shortcuts
