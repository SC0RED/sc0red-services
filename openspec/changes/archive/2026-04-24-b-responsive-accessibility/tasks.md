# Tasks: Responsive & Accessibility

## Responsive CSS

- [x] Add 480px breakpoint to globals.css (compact mobile — stack grids, reduce padding)
- [x] Make dashboard stats grid responsive: repeat(4,1fr) → auto-fit minmax(200px,1fr)
- [x] Make dashboard tables scrollable on mobile (add overflowX: auto)
- [x] Make signup two-column grids responsive (stack on <480px)
- [x] Make comparison view grids responsive (stack on mobile)

## Accessibility

- [x] Add aria-live="polite" to ScanProgressPhase progress container
- [x] Add aria-hidden="true" to decorative SVGs in DashboardSidebar nav items
- [x] Replace <img> tags with next/image in 4 locations (login, signup, landing, sidebar)

## Tests

- [x] Verify all existing tests still pass after changes
