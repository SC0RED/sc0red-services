> **Status: blocked on leadership input.** See `proposal.md` "Open Questions for Leadership" — at minimum §1 (final name), §2 (tagline), and §3 (logo asset) must be answered before Phase 1 can begin. Phase 2 additionally needs §4 (Cognito split-brain acceptable?), §6 (hostname pattern), §10 (90-day dual-serve). Phase 3 needs §9 (reorder direction against the current post-#250 layout).
>
> Tasks are grouped by phase. Each phase ships as its own PR.

---

# Phase 1 — vector-advisory-brand-text

*Customer-facing brand on the existing Janus host. Reversible. Low risk.*

**Blocked on**: Open Questions §1, §2, §3, §7, §8.

## P1.1 Brand asset & copy preparation

- [ ] P1.1.1 Receive the final product name from leadership (Open Question §1) and the tagline (§2). Capture both as agreed strings in `design.md` Decisions.
- [ ] P1.1.2 Receive the Vector Advisory logo asset (`vector-advisory-logo.png` and/or `.svg`) from leadership / design (Open Question §3). If unavailable, agree with leadership to ship typographic-only wordmark for v1 — log the decision and add the icon as a small follow-up commit later.
- [ ] P1.1.3 Resolve Open Question §7 (email "from" sender display name) and §8 (CSS palette source of truth). If §8 = Figma → extract the token list. If §8 = visual audit → capture as a short note in `visual/sc0red-design-tokens.md`.

## P1.2 Bulk find-and-replace pass (mechanical)

- [ ] P1.2.1 Run `git grep -l "Janus"` over the repository to enumerate every occurrence. Generate a report committed as `visual/janus-occurrences-pre.txt` for traceability.
- [ ] P1.2.2 Apply substitution `Janus → Vector Advisory` across the customer-visible scope only:
  - **Include**: `frontend/src/app/**/*.tsx`, `frontend/src/components/**/*.tsx` (excluding tests), `frontend/src/lib/auth/**`, `frontend/src/lib/hooks/useTheme.ts`, `backend/src/handlers/templates/*.html`, `README.md`, `DOCUMENTATION.md`.
  - **Exclude (no substitution)**: `infrastructure/**`, `backend/scripts/**`, `backend/tests/**`, `frontend/src/tests/**`, `frontend/e2e/**` (URLs handled in Phase 2), `*.lock`, `cdk.out/**`, `.git/**`, `node_modules/**`, `package.json` / `pyproject.toml` (package names stay), `docker-compose*.yml` (container names stay), `.gitleaks.toml`.
- [ ] P1.2.3 Inspect the diff after the bulk pass — flag any substitution that looks wrong (e.g., a comment that referenced "the Janus codebase" in a structural sense). Revert false positives.

## P1.3 Hand-curated headline copy

- [ ] P1.3.1 Update page titles in `frontend/src/app/layout.tsx` and any per-route metadata blocks (`dashboard/page.tsx`, `recently-deleted/page.tsx`, etc.) — final wording from P1.1.1.
- [ ] P1.3.2 Rewrite the marketing landing page hero, body copy, and footer in `frontend/src/app/page.tsx` to reflect Vector Advisory positioning. Include the "AI tools + advisory for mid-market PE" framing where appropriate.
- [ ] P1.3.3 Update `backend/src/handlers/templates/invitation_email.html` — subject line, body copy, footer block. Verify the rendered email previews correctly (spawn a test invitation locally; eyeball the output).
- [ ] P1.3.4 Replace logo file references: rename `frontend/public/janus-logo.png` to `frontend/public/vector-advisory-logo.png` (or the asset filename agreed in P1.1.2). Update `<img src=... alt="Janus">` → `<img src="/vector-advisory-logo.png" alt="Vector Advisory">` in all 5 component sites.
- [ ] P1.3.5 Update the `useTheme.ts` docstring and any module-level docs that surface to developer-onboarding. CLAUDE.md header retitled.
- [ ] P1.3.6 Add a dedicated paragraph in `CLAUDE.md` and `README.md` titled **"Naming convention: Vector Advisory (customer) vs. janus (internal)"** explaining that the customer-facing name is Vector Advisory but every AWS resource, CDK stack, package name, and the GitHub repo retains `janus-*` for historical reasons — this is intentional, not a TODO.

## P1.4 CSS / brand palette alignment

- [ ] P1.4.1 Compare `frontend/src/app/globals.css` (and any per-component overrides) against the sc0red.com tokens captured in P1.1.3. List divergences.
- [ ] P1.4.2 Update primary palette tokens (`--accent-blue`, `--accent-blue-glow`, etc.) where they materially diverge. Stay scoped to global CSS variables; do NOT restyle individual components.
- [ ] P1.4.3 Update typography tokens (font family, scale) if the company site uses different fonts — check `next/font` import in `layout.tsx`.
- [ ] P1.4.4 Visual smoke check across login page, dashboard, analysis detail, and the marketing landing page in both light and dark themes. Capture before/after screenshots in `visual/css-alignment/{before,after}/`.

## P1.5 Quality gates + ship

- [ ] P1.5.1 `cd frontend && npm run lint` clean; `npx tsc --noEmit` clean; `npm test` all green.
- [ ] P1.5.2 `cd backend && uv run ruff check src/` clean; `uv run pytest tests/ -q` all green; coverage ≥ 95%.
- [ ] P1.5.3 Architecture-reviewer agent on the diff. Resolve all CRITICAL findings; address or defer MEDIUM findings.
- [ ] P1.5.4 Open PR `feat/vector-advisory-brand-text` against `development`. Include before/after screenshots (sidebar, marketing page, login).
- [ ] P1.5.5 Merge to `development`. Soak 24h on dev.janus.sc0red.com (page now says Vector Advisory but URL is still Janus — expected during Phase 1 soak).

---

# Phase 2 — vector-advisory-host-cutover

*Live-infrastructure change. Risky. Sequenced after Phase 1.*

**Blocked on**: Open Questions §4, §6, §10. Should also wait for Phase 1 to soak so the brand text is already correct on the new host when traffic flips.

## P2.1 Infrastructure: new hosts, ACM cert, Cognito allowlist

- [ ] P2.1.1 In `infrastructure/stacks/amplify_construct.py`, add per-environment Vector hostnames (`dev.vector.sc0red.com`, `testing.vector.sc0red.com`, `vector.sc0red.com`) as Amplify branch domains. The old Janus hostnames stay configured (for the redirect step) but switch to redirect-mode after P2.3.
- [ ] P2.1.2 Update Cognito allowed redirect URIs and logout URIs in `infrastructure/stacks/cognito_construct.py` to include the new hosts. **Both old and new hosts SHALL be allowed during the 90-day cutover window.**
- [ ] P2.1.3 Update CDK environment configs in `infrastructure/app.py` to read the new `FRONTEND_DOMAIN` (the Vector hostname) per environment. Variable name stays `FRONTEND_DOMAIN`; only the value changes.
- [ ] P2.1.4 ACM cert: ensure the new hosts are covered. Recommended: wildcard `*.vector.sc0red.com`. Request and validate before P2.2.

## P2.2 Frontend NextAuth + e2e setup

- [ ] P2.2.1 Update NextAuth configuration in the frontend if it depends on a hardcoded host (search `frontend/src/` for `janus.sc0red.com` / `dev.janus.sc0red.com` literals).
- [ ] P2.2.2 Update Playwright E2E setup files in `frontend/e2e/` that reference the Janus host. Test fixtures pointing at `dev.janus.sc0red.com` flip to `dev.vector.sc0red.com`.

## P2.3 Cutover gate

- [ ] P2.3.1 Verify on `dev.vector.sc0red.com` that login + scan + analysis + PDF export all work end-to-end. Both hosts are serving at this point — the Vector host is the new home; the Janus host is still serving in parallel.
- [ ] P2.3.2 Configure the old Janus Amplify domains (`dev.janus.sc0red.com` etc.) to serve HTTP 301 redirects to the matching Vector path. Verify with `curl -I -L` that the redirect chain resolves correctly.
- [ ] P2.3.3 Document the 90-day decommission window in `visual/notes.md` with a calendar reminder for the Janus host removal task (P2.6.1).

## P2.4 Document propagation

- [ ] P2.4.1 Update the company website (separate repo, `sc0red.github.io/website-redux`) to link to the new Vector URL in the Vector Advisory product entry.
- [ ] P2.4.2 Update README, CLAUDE.md, and any internal docs referencing the old host. (CLAUDE.md was already retitled in Phase 1; this is host-string updates only.)

## P2.5 Quality gates + ship

- [ ] P2.5.1 `cd infrastructure && uv run cdk synth` — synth succeeds without diff that recreates AWS resources. **CRITICAL CHECK**: if `cdk diff` shows a Lambda / table / queue replace, STOP — find the rogue rename.
- [ ] P2.5.2 `cd frontend && npm test` — Playwright e2e setup updates pass.
- [ ] P2.5.3 Smoke-test login on a preview build before cutover. Cognito + NextAuth callback end-to-end.
- [ ] P2.5.4 Open PR `feat/vector-advisory-host-cutover` against `development`. Include the redirect smoke-test output and the cdk-diff "no resource recreation" verification.
- [ ] P2.5.5 Merge to `development`. Promote dev → testing → production with redirects following the same per-env order.

## P2.6 Decommission window

- [ ] P2.6.1 90 days post-production-cutover, remove the old Janus hosts (Amplify domain config + Route 53 records) and remove the old Cognito redirect URIs. Open a separate `chore/decommission-janus-hosts` PR.

---

# Phase 3 — analysis-page-advisory-reorder

*Independent of brand work. Section ordering decision against today's layout (post-PR #250). Reversible.*

**Blocked on**: Open Question §9. Phase 3 is independent of Phases 1 and 2 and can ship in any order relative to them.

## P3.1 Design re-validation

- [ ] P3.1.1 Receive Open Question §9 answer from leadership: against the current layout (post-PR #250 with executive strap + strategy map + deep-dive CTA), what reorder do we want?
- [ ] P3.1.2 Update `specs/polished-pdf-export/spec.md` and the `analysis-detail-narrative` canonical-spec delta to encode the leadership-confirmed order. Add an `analysis-detail-narrative` MODIFIED Requirement covering the section-ordering scenario (does NOT exist in the current artifact; needs adding now that the world has moved).

## P3.2 Implementation

- [ ] P3.2.1 In `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx`, reorder the JSX below the `<TopActionsCallout />` block per P3.1.1. Conditional render guards (`{data.valueChain && data.valueChain.steps.length > 0 && …}`, `{data.ebitdaTree && …}`) move with their components.
- [ ] P3.2.2 In `frontend/src/app/print/[analysisId]/PrintReport.tsx`, mirror the on-screen reorder. PDF section break rules (`print-section--break-before`) move with their components.

## P3.3 Tests

- [ ] P3.3.1 Update the existing `frontend/src/tests/pages/AnalysisDetail.test.tsx` section-order assertions (test IDs of `analysis-section-{name}` already exist per PR #250 — assert the new order via `getAllByTestId`).
- [ ] P3.3.2 Update `frontend/src/tests/components/print/PrintReport.test.tsx` to reflect the new section order.
- [ ] P3.3.3 Run the full frontend test suite — all tests pass.

## P3.4 Visual verification (mirrors improve-pdf-export-content §7)

- [ ] P3.4.1 Pick three representative analyses (sparse / mid-size / deep EBITDA — same selection criteria as the PDF rebuild). Capture before-PDFs (current development state) and store under `visual/before/`.
- [ ] P3.4.2 After implementation, capture after-PDFs from the rebranded development environment. Store under `visual/after/`.
- [ ] P3.4.3 Page-by-page diff: confirm new section order. Document any deviations in `visual/notes.md`.

## P3.5 Quality gates + ship

- [ ] P3.5.1 `cd frontend && npm run lint && npx tsc --noEmit && npm test` — all clean.
- [ ] P3.5.2 Architecture-reviewer agent on the diff. The diff is small (two files reordered) so review focus is "did anything besides JSX position change?"
- [ ] P3.5.3 Open PR `feat/analysis-page-advisory-reorder` against `development`. Include before/after PDF screenshots.
- [ ] P3.5.4 Merge to `development`. Promote dev → testing → production.

---

# Cross-phase rollout coordination

- [ ] X.1 After Phase 1 + Phase 2 ship, archive this change once the spec deltas are synced. Phase 3 can ship before or after archive depending on §9 timing.
- [ ] X.2 90-day decommission task (P2.6.1) is the only follow-up that crosses outside this proposal's scope.

---

# Order of operations summary

```
                      Open Q §1, §2, §3, §7, §8 answered
                                  ↓
                  Phase 1 — vector-advisory-brand-text
                                  ↓
                            soak on dev.janus
                                  ↓
                    Open Q §4, §6, §10 answered
                                  ↓
                  Phase 2 — vector-advisory-host-cutover
                                  ↓
                        cutover + 90-day window
                                  ↓
                          decommission janus hosts

  In parallel (any time after Open Q §9 answered):
                  Phase 3 — analysis-page-advisory-reorder
```
