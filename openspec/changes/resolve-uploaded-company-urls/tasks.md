# Tasks — Resolve URLs for name-only uploaded companies

**Status: backlog / not scheduled.** Companion to the shipped honest fix
(url-less rows unselectable + exclusion note, no silent drop). This change makes
name-only uploads actually analyzable.

- [ ] 0. UX decision: resolve-on-upload vs. an explicit "Find URLs for N" action
  on the confirm screen; confidence threshold for auto-accept vs. confirm.
- [ ] 1. Resolution step: name → official URL via the grounded-search path;
  emit candidates into the needs-validation tier (tagged source `upload`).
- [ ] 2. Confirm-screen affordance to trigger resolution + review/edit results
  before analysis.
- [ ] 3. Confidence handling: auto-accept high-confidence, surface
  low-confidence/ambiguous for customer choice; never silently mis-resolve.
- [ ] 4. Tests (resolution happy path, ambiguous→confirm, unresolved stays
  excluded) + E2E + PR.
