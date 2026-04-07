# Tasks: Performance Baselines

## Frontend Instrumentation

- [x] Create `frontend/src/lib/reportWebVitals.ts` — Web Vitals collection + console logging
- [x] Wire Web Vitals into app layout
- [x] Add `@next/bundle-analyzer` dev dependency + configure in next.config.js
- [x] Run bundle analyzer and document current sizes

## Backend Instrumentation

- [x] Add request duration logging to API handler (method + path + status + ms)
- [x] Verify StepTimer output is logged to CloudWatch (already done — request_executor.py lines 162-182)

## Baselines

- [x] Create `docs/baselines/README.md` with baseline numbers template
