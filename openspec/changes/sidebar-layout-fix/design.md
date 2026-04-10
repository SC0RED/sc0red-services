## Context

Currently every authenticated page independently renders `<DashboardSidebar />`:

```
app/layout.tsx (SessionWrapper)
  ├── dashboard/layout.tsx (SessionProvider — duplicate)
  │   └── dashboard/page.tsx → <DashboardSidebar /> + <main>content</main>
  ├── scan/new/page.tsx → <SessionWrapper> + <DashboardSidebar /> + <main>
  ├── analyses/page.tsx → <DashboardSidebar /> + <main>
  ├── team/page.tsx → <SessionWrapper> + <DashboardSidebar /> + <main>
  ├── analysis/[id]/AnalysisDetail.tsx → <DashboardSidebar /> + <main>
  └── portfolio/[scanId]/page.tsx → <DashboardSidebar /> + <main>
```

On navigation, Next.js unmounts the entire old page tree and mounts the new one. The sidebar remounts, `useSession()` re-initializes, and the Team icon flickers.

## Goals / Non-Goals

**Goals:**
- Sidebar persists across all authenticated page navigations (zero remounts)
- Eliminate Team icon flicker
- Remove duplicate SessionProvider/SessionWrapper wrappers
- Clean up page files to only contain page-specific content

**Non-Goals:**
- Changing sidebar visual design or behavior
- Changing route URLs (route groups don't affect URLs)
- Modifying authentication logic

## Decisions

### 1. Use Next.js route group `(authenticated)` for shared layout

**Decision: Create `app/(authenticated)/layout.tsx` with sidebar + main wrapper.**

Next.js route groups (parenthesized folders) share a layout without adding a URL segment. All authenticated pages move under this group.

```
app/layout.tsx (SessionWrapper, RouteProgress)
  └── app/(authenticated)/layout.tsx (DashboardSidebar + main wrapper)
      ├── dashboard/page.tsx (content only)
      ├── scan/new/page.tsx (content only)
      ├── analyses/page.tsx (content only)
      ├── team/page.tsx (content only)
      ├── analysis/[analysisId]/page.tsx (content only)
      └── portfolio/[scanId]/page.tsx (content only)
```

Alternative considered: Keep sidebar in each page but wrap in a higher-level context to prevent remount. This would be more complex and fight against the framework's layout model.

### 2. Layout renders sidebar + main element

**Decision: The authenticated layout provides the full page shell.**

```tsx
// app/(authenticated)/layout.tsx
export default function AuthenticatedLayout({ children }) {
    return (
        <>
            <DashboardSidebar />
            <main id="main" className="page-content">
                <Breadcrumbs />
                {children}
            </main>
        </>
    )
}
```

Pages then only return their content — no sidebar, no `<main>`, no breadcrumbs.

Note: Some pages use `page-content`, others `page-content-narrow`, others `page-content-wide`. The layout will use a default, and pages that need a different width can wrap their content in a div with the appropriate class.

### 3. Delete dashboard/layout.tsx and dashboard/providers.tsx

**Decision: Remove the duplicate SessionProvider.**

Root `layout.tsx` already wraps everything in `SessionWrapper` (which is `SessionProvider`). The dashboard-specific `layout.tsx` → `providers.tsx` → `SessionProvider` nesting is redundant and can cause session re-fetch cycles.

### 4. Revert the useRef role cache from PR #143

**Decision: Remove the workaround since the root cause is fixed.**

With the sidebar living in a persistent layout, `useSession()` never re-initializes during navigation. The `useRef` cache and the `useRef` import are no longer needed.

## Risks / Trade-offs

- **Page-specific main classes**: Some pages use different content widths (`page-content-narrow`, `page-content-wide`). The layout must accommodate this without breaking existing styling. → Mitigation: Layout uses default width; pages override with a wrapper div when needed.
- **Team page server-side auth check**: `team/page.tsx` has `getServerSession()` + redirect for non-admins. This stays in the page — the layout doesn't handle authorization. → No change needed.
- **Breadcrumbs**: Currently some pages render `<Breadcrumbs />` and some don't (dashboard doesn't). → The layout can render breadcrumbs, and dashboard can suppress them via the existing breadcrumb logic that hides on `/dashboard`.
