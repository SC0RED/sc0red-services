## Why

The Team icon in the sidebar flickers (disappears and reappears) during client-side navigation between Dashboard, New Scan, and other pages. This happens because every page renders its own `<DashboardSidebar />` instance — when Next.js navigates, it unmounts the old page's sidebar and mounts a new one. During this remount, `useSession()` returns undefined momentarily, causing the `adminOnly` filter to drop the Team link. A `useRef` cache (PR #143) didn't fix it because the ref is destroyed with the component on unmount.

The fix is structural: move the sidebar into a shared Next.js layout so it persists across page navigations without remounting.

## What Changes

- **New shared layout**: Create `app/(authenticated)/layout.tsx` that renders `<DashboardSidebar />` once for all authenticated routes
- **Move pages**: Relocate `dashboard`, `scan`, `analyses`, `analysis`, `portfolio`, and `team` under the `(authenticated)` route group
- **Strip sidebar from pages**: Remove `<DashboardSidebar />` imports and rendering from all 6 page files
- **Remove duplicate SessionProviders**: Delete `dashboard/layout.tsx` and `dashboard/providers.tsx` (root layout already provides SessionWrapper)
- **Remove SessionWrapper** from individual pages (`scan/new`, `team`) that wrap redundantly
- **Revert useRef workaround**: Remove the role caching from PR #143 since the root cause is fixed

## Capabilities

### New Capabilities
- `authenticated-layout`: Shared layout for all authenticated pages that renders the sidebar once and persists it across navigation

### Modified Capabilities

## Impact

- **Files moved**: 6 page directories move under `app/(authenticated)/`
- **Files deleted**: `dashboard/layout.tsx`, `dashboard/providers.tsx`
- **Files modified**: All 6 page files (remove sidebar + SessionWrapper), `DashboardSidebar.tsx` (revert useRef)
- **No API changes**: Routes stay the same — `(authenticated)` is a route group (parentheses), not a URL segment
- **No test changes expected**: Component behavior is identical, just mounted differently
