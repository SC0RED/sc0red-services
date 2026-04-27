# toast-notifications Specification

## Purpose
TBD - created by archiving change webapp-ux-foundations-tier1. Update Purpose after archive.
## Requirements
### Requirement: App provides ephemeral feedback via toast notifications

The webapp SHALL render a global toast notification surface that any component can dispatch to via a `useToast()` hook. Toasts SHALL appear in the bottom-right viewport corner and stack vertically (newest on top of the stack). The system SHALL support four variants: `success`, `error`, `info`, `loading`.

#### Scenario: Success toast auto-dismisses after 4 seconds

- **WHEN** a component calls `toast.success("Deleted")` and the user does not interact with it
- **THEN** the toast appears in the bottom-right corner, persists for ~4 seconds, then fades out

#### Scenario: Error toast persists until dismissed

- **WHEN** a component calls `toast.error("Failed to delete")`
- **THEN** the toast appears with a close button and remains visible until the user clicks the close button or another action triggers dismissal — it does NOT auto-dismiss

#### Scenario: Multiple toasts stack vertically

- **WHEN** three toasts are dispatched in rapid succession
- **THEN** the toasts render stacked in the bottom-right corner, with the newest on top, each visually distinct

#### Scenario: Loading toast can be promoted to success or error

- **WHEN** a component dispatches `toast.loading("Re-analyzing...")` to get a `toastId`, awaits a network call, then calls `toast.update(toastId, { variant: 'success', message: 'Re-analysis queued' })`
- **THEN** the original loading toast morphs to a success toast in place; no second toast appears

### Requirement: Destructive actions support Undo via deferred commit

When a user performs a destructive action (delete analysis, delete scan), the toast notification SHALL include an "Undo" affordance that is interactive for 5 seconds. The destructive API call SHALL NOT execute until the 5-second window expires (or the user dismisses the toast). Clicking "Undo" within the window SHALL cancel the action with no API call made.

#### Scenario: User undoes a deletion within 5 seconds

- **WHEN** the user clicks "Delete" on an analysis row, then clicks "Undo" in the resulting toast within 4 seconds
- **THEN** no DELETE API request is sent and the analysis remains in the list

#### Scenario: User waits past the Undo window

- **WHEN** the user clicks "Delete" on an analysis row and does not click Undo
- **THEN** after 5 seconds, the DELETE API request fires; on success the row remains removed; on failure an error toast surfaces

#### Scenario: User dismisses the toast before the window expires

- **WHEN** the user clicks "Delete", then clicks the toast's close button at 2 seconds
- **THEN** the deletion commits immediately (the user has explicitly acknowledged they don't want to undo)

### Requirement: Toasts honor accessibility primitives

Toast notifications SHALL use ARIA roles appropriate to their semantic intent: `role="status"` for success/info/loading variants, `role="alert"` for error variants. Slide-in animations SHALL respect `prefers-reduced-motion: reduce` (collapse to instant render). The close button SHALL be keyboard-focusable and labelled.

#### Scenario: Screen reader announces success quietly

- **WHEN** a success toast renders
- **THEN** the toast container has `role="status"` (polite live region — does not interrupt)

#### Scenario: Screen reader announces error assertively

- **WHEN** an error toast renders
- **THEN** the toast container has `role="alert"` (assertive live region — interrupts current speech)

#### Scenario: Reduced-motion user sees instant toasts

- **WHEN** the user has `prefers-reduced-motion: reduce` set
- **THEN** the toast appears without slide-in animation; opacity-only change applies

#### Scenario: Keyboard user can dismiss

- **WHEN** the user navigates to the toast's close button via Tab and presses Enter
- **THEN** the toast dismisses
