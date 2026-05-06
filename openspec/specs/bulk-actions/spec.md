# bulk-actions Specification

## Purpose

Multi-row selection on the analyses table with bulk delete via Toast Undo. Selection state lives only as long as the visible context: changing filters, search, or navigating away clears it to prevent accidental "delete from invisible filtered set" surprises.

## Requirements

### Requirement: Analyses table supports row selection

The `/analyses` table SHALL render a checkbox column on the left of each row. Clicking a checkbox toggles selection of that row. A header checkbox toggles selection of all currently-visible rows (loaded + matching filters).

#### Scenario: User selects a single row

- **WHEN** the user clicks the checkbox on a single row
- **THEN** the row visually indicates it is selected (e.g., highlighted background); a sticky toolbar appears showing "1 selected"

#### Scenario: Header checkbox selects all visible

- **WHEN** the user clicks the header checkbox with 50 visible rows
- **THEN** all 50 rows become selected; the toolbar shows "50 selected"

#### Scenario: Header checkbox deselects all when all visible are selected

- **WHEN** all visible rows are already selected and the user clicks the header checkbox
- **THEN** all selections clear; the toolbar disappears

### Requirement: Shift-click selects a range

The analyses table SHALL support shift-click range selection: clicking row A's checkbox, then shift-clicking row B's checkbox, selects all rows between A and B inclusive.

#### Scenario: User shift-clicks a range

- **WHEN** the user clicks the checkbox on row 3, then shift-clicks the checkbox on row 7
- **THEN** rows 3, 4, 5, 6, and 7 are all selected; the toolbar shows "5 selected"

### Requirement: Bulk delete with Toast Undo

The selection toolbar SHALL include a "Delete N" button. Clicking it SHALL trigger a Toast Undo (per Tier 1 `toast-notifications` spec) with a 5-second window. The DELETE API SHALL NOT fire until the window expires; clicking Undo cancels the action with no API call.

#### Scenario: User bulk deletes with undo

- **WHEN** the user has 8 rows selected and clicks "Delete 8"
- **THEN** a toast appears with "Deleted 8 analyses. Undo?" and a 5-second timer; the rows visually disappear from the table; if the user does not click Undo, the DELETE requests fire after 5s

#### Scenario: User undoes bulk delete

- **WHEN** the user clicks "Delete 8" and clicks "Undo" within 5 seconds
- **THEN** no DELETE requests are made; the rows remain in the table

### Requirement: Selection clears on context change

Selection state SHALL clear when the user changes the filter set, changes search query, or navigates away from `/analyses`. This prevents accidental "delete from invisible filtered set" surprises.

#### Scenario: Filter change clears selection

- **WHEN** the user has 5 rows selected and changes the tier filter
- **THEN** the selection clears; the toolbar disappears

#### Scenario: Search clears selection

- **WHEN** the user has rows selected and types a search query
- **THEN** the selection clears
