# Janus Improvement Roadmap

## Execution Order

```
0. Performance Baselines     [LOW effort]    ← Capture before/after numbers
   ↓
D. Backend Hardening         [LOW effort]    ← Quick wins, improves API contract
   ↓
A. UI Component Library      [HIGH effort]   ← Foundation for all frontend work
   ↓
B. Responsive & Accessibility [MED effort] ←→ C. Data Fetching & Performance [MED effort]
   ↓                                            (can run in parallel)
E. Navigation & UX Polish    [MED effort]
   ↓
F. Styling Migration         [HIGH effort]   ← Incremental, alongside other work
```

## Proposals

| Package | Impact | Effort | Status | Description |
|---|---|---|---|---|
| [0: Performance Baselines](0-performance-baselines/proposal.md) | Prerequisite | Low | Proposed | Web Vitals, Lighthouse, bundle analysis, X-Ray baselines |
| [D: Backend Hardening](d-backend-hardening/proposal.md) | Medium | Low | Proposed | Org auth middleware, error codes, correlation IDs, request timing |
| [A: UI Component Library](a-ui-component-library/proposal.md) | High | High | Proposed | Button, Input, Modal, Skeleton, FormField + migration |
| [B: Responsive & A11y](b-responsive-accessibility/proposal.md) | High | Medium | Proposed | Breakpoints, responsive grids, ARIA live, next/image |
| [C: Data Fetching & Perf](c-data-fetching-performance/proposal.md) | High | Medium | Proposed | SWR, polling backoff, lazy loading, DynamoDB pagination |
| [E: Navigation & UX Polish](e-navigation-ux-polish/proposal.md) | Medium | Medium | Proposed | Breadcrumbs, custom modals, error recovery, component splitting |
| [F: Styling Migration](f-styling-migration/proposal.md) | Lower | High | Proposed | Utility classes, incremental inline style removal |
