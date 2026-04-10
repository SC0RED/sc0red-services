## 1. Create shared authenticated layout

- [x] 1.1 Create `app/(authenticated)/layout.tsx` with DashboardSidebar + main wrapper + Breadcrumbs
- [x] 1.2 Move `app/dashboard/` to `app/(authenticated)/dashboard/`
- [x] 1.3 Move `app/analyses/` to `app/(authenticated)/analyses/`
- [x] 1.4 Move `app/scan/` to `app/(authenticated)/scan/`
- [x] 1.5 Move `app/team/` to `app/(authenticated)/team/`
- [x] 1.6 Move `app/analysis/` to `app/(authenticated)/analysis/`
- [x] 1.7 Move `app/portfolio/` to `app/(authenticated)/portfolio/`

## 2. Strip sidebar and wrappers from pages

- [x] 2.1 Remove DashboardSidebar, main wrapper, Breadcrumbs from dashboard/page.tsx
- [x] 2.2 Remove DashboardSidebar, SessionWrapper, main wrapper, Breadcrumbs from scan/new/page.tsx
- [x] 2.3 Remove DashboardSidebar, main wrapper, Breadcrumbs from analyses/page.tsx
- [x] 2.4 Remove DashboardSidebar, SessionWrapper, main wrapper, Breadcrumbs from team/page.tsx
- [x] 2.5 Remove DashboardSidebar, main wrapper, Breadcrumbs from analysis/[analysisId]/AnalysisDetail.tsx
- [x] 2.6 Remove DashboardSidebar, main wrapper, Breadcrumbs from portfolio/[scanId]/page.tsx

## 3. Remove duplicate session providers

- [x] 3.1 Delete `app/dashboard/layout.tsx` and `app/dashboard/providers.tsx`

## 4. Revert useRef workaround

- [x] 4.1 Remove useRef role cache from DashboardSidebar.tsx (revert PR #143 changes), restore original filter using session directly

## 5. Verify

- [x] 5.1 Run `npm test` — all unit tests pass (389 tests, 1 removed — sidebar/SessionWrapper test no longer applicable)
- [x] 5.2 Run `npm run lint` and `npx tsc --noEmit` — no errors
- [ ] 5.3 Run `./scripts/playwright.sh --mode=local` — all E2E tests pass
- [ ] 5.4 Manual: navigate between pages — no sidebar flicker
