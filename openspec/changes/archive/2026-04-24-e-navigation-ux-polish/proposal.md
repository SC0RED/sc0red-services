# Package E: Navigation & UX Polish

**Impact**: Medium | **Effort**: Medium | **Priority**: After Packages B and C

## Problem

Navigation is flat — just a sidebar with links. No breadcrumbs, no progress indicators during transitions, no undo for destructive actions. Two components are near the 360-line limit and need splitting. Error recovery is poor — generic messages with no retry or guidance.

## Proposal

Polish the user experience with better navigation, smarter error handling, and component cleanup.

## Changes

### 1. Breadcrumb navigation

Add a `Breadcrumbs` component that renders the current path:
- Dashboard
- Dashboard → Analyses → Acme Corp Analysis
- Dashboard → Scans → Portfolio Scan #3
- Dashboard → Team

Derive from the URL path + page data. Show below the sidebar on desktop, below the header on mobile.

### 2. Custom delete modals (uses Package A's ConfirmDialog)

Replace all browser `confirm()` calls with `ConfirmDialog`:
- Delete analysis (currently in `DeleteAnalysisButton.tsx`)
- Delete scan (currently in `DeleteScanButton.tsx`)
- Remove team member
- Revoke invitation

### 3. Error recovery

Improve error messages with:
- **Retry buttons** on failed operations (fetch, delete, upload)
- **Contextual guidance** ("Check your connection", "Try a different password")
- **Toast notifications** for transient success/error (instead of inline alerts that disappear on re-render)

### 4. Component splitting

Break down large components:
- `OpportunitiesList.tsx` (356 lines) → Extract filter bar, opportunity card, expansion panel
- `DashboardSidebar.tsx` (348 lines) → Extract navigation items, user profile section, mobile overlay

### 5. Page transition indicators

Show a subtle progress bar (like YouTube/GitHub) at the top of the page during route transitions. Next.js supports this via `usePathname` + NProgress or a simple custom component.

## What we DON'T do

- No full navigation redesign
- No animation library
- No toast library (simple CSS-based component)
- No undo for deletes (complex, low ROI for now)

## Success criteria

- [ ] Breadcrumbs visible on all authenticated pages
- [ ] All destructive actions use custom dialog (no browser confirm)
- [ ] Failed operations show retry button
- [ ] OpportunitiesList and DashboardSidebar under 250 lines each
- [ ] Route transitions show progress indicator
