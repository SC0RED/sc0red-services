## ADDED Requirements

### Requirement: The command palette is discoverable and can open the shortcuts help

The command palette SHALL be discoverable by a user who does not already know the `⌘K` / `Ctrl-K` shortcut. The authenticated sidebar SHALL show a persistent, unobtrusive (muted, small) affordance that opens the command palette on click. The palette SHALL also include a "Keyboard shortcuts" action that opens the keyboard-shortcuts help modal, so palette users can find the full shortcut list.

#### Scenario: A mouse user opens the palette from the sidebar

- **WHEN** the user clicks the "commands" affordance in the sidebar footer
- **THEN** the command palette opens (the same palette `⌘K` / `Ctrl-K` opens)

#### Scenario: The palette can open the shortcuts help

- **WHEN** the user opens the command palette and selects the "Keyboard shortcuts" action
- **THEN** the keyboard-shortcuts help modal opens
