## 1. Brand asset & copy preparation

- [ ] 1.1 Confirm the final product name with leadership ("Vector Advisory" vs. "Vector"), the tagline ("AI Risk & Strategic Intelligence" placeholder), and the email-footer phrasing. Capture the agreed strings in `design.md` Open Questions before any code change.
- [ ] 1.2 Obtain the Vector Advisory logo asset (`vector-advisory-logo.png` and/or `.svg`) from leadership / design. If unavailable by implementation start, ship with a typographic-only wordmark and add the icon in a small follow-up commit.
- [ ] 1.3 Audit `https://sc0red.github.io/website-redux/` for the design language: extract primary palette, typography, spacing scale, accent treatment. Capture as a short note in this folder (`visual/sc0red-design-tokens.md`) so the CSS-alignment task has a reference.

## 2. Bulk find-and-replace pass (mechanical)

- [ ] 2.1 Run `git grep "Janus"` over the repository to enumerate every occurrence. Generate a report committed as `visual/janus-occurrences-pre.txt` for traceability.
- [ ] 2.2 Apply substitution `Janus → Vector Advisory` (and `janus → vector-advisory` ONLY for url path segments) across **the customer-visible scope only**:
   - Include: `frontend/src/app/**/*.tsx`, `frontend/src/components/**/*.tsx` (excluding tests), `frontend/src/lib/auth/**`, `frontend/src/lib/hooks/useTheme.ts`, `backend/src/handlers/templates/*.html`, `README.md`, `DOCUMENTATION.md`.
   - Exclude (no substitution): `infrastructure/**`, `backend/scripts/**`, `backend/tests/**`, `frontend/src/tests/**`, `frontend/e2e/**` setup files (URLs handled separately), `*.lock`, `cdk.out/**`, `.git/**`, `node_modules/**`, `package.json` / `pyproject.toml` (package names stay), `docker-compose*.yml` (container names stay), `.gitleaks.toml`.
- [ ] 2.3 Inspect the diff after the bulk pass — flag any substitution that looks wrong (e.g., a comment that referenced "the Janus codebase" in a structural sense rather than the brand). Revert any false positives.

## 3. Hand-curated headline copy

- [ ] 3.1 Update page titles in `frontend/src/app/layout.tsx` and any per-route metadata blocks (`dashboard/page.tsx`, `recently-deleted/page.tsx`, etc.) — final wording per task 1.1.
- [ ] 3.2 Rewrite the marketing landing page hero, body copy, and footer in `frontend/src/app/page.tsx` to reflect Vector Advisory positioning. Include the "AI tools + advisory for mid-market PE" framing where appropriate.
- [ ] 3.3 Update `backend/src/handlers/templates/invitation_email.html` — subject line, body copy, footer block. Verify the rendered email previews correctly (spawn a test invitation locally; eyeball the output).
- [ ] 3.4 Replace logo file references: rename `frontend/public/janus-logo.png` to `frontend/public/vector-advisory-logo.png` (or the asset filename agreed in 1.2). Update `<img src=... alt="Janus">` → `<img src="/vector-advisory-logo.png" alt="Vector Advisory">` in all 5 component sites.
- [ ] 3.5 Update the `useTheme.ts` docstring and any module-level docs that surface to developer-onboarding (CLAUDE.md header retitled "Vector Advisory — Claude Code Instructions").
- [ ] 3.6 Add a dedicated paragraph in `CLAUDE.md` and `README.md` titled **"Naming convention: Vector Advisory (customer) vs. janus (internal)"** explaining that the customer-facing name is Vector Advisory but every AWS resource, CDK stack, package name, and the GitHub repo retains `janus-*` for historical reasons — this is intentional, not a TODO.

## 4. Analysis page section reorder

- [ ] 4.1 In `frontend/src/app/(authenticated)/analysis/[analysisId]/AnalysisDetail.tsx`, reorder the JSX below the `<TopActionsCallout />` block so the section flow is: Top Actions → ValueChainDiagram → EbitdaSection → RiskBreakdown → ValueLeverSummary + OpportunitiesList + Sc0redCTABanner → re-analysis state + DocumentUpload (footer).
- [ ] 4.2 Verify the conditional render guards (`{data.valueChain && data.valueChain.steps.length > 0 && …}`, `{data.ebitdaTree && …}`) move with their components and remain in place.
- [ ] 4.3 Update the existing `tests/pages/AnalysisDetail.test.tsx` (if any present-section assertions encode order). Sub-component render assertions should not need changes; new section-order test if useful.
- [ ] 4.4 Visually verify on `npm run dev` that the page reads correctly in the new order on a populated analysis and on a sparse one (no value chain / no ebitda).

## 5. PDF section reorder

- [ ] 5.1 In `frontend/src/app/print/[analysisId]/PrintReport.tsx`, reorder the print components: Cover → Executive Summary → Top Actions → **PrintValueChainList → PrintEbitdaOutline → PrintRiskTable → PrintOpportunityList** → Methodology Appendix → Back Cover.
- [ ] 5.2 Update `frontend/src/tests/components/print/PrintReport.test.tsx` to reflect the new section order. Keep the empty-everything smoke test; just update expected order assertions.
- [ ] 5.3 Run the full frontend test suite (`cd frontend && npm test`) — all 784+ tests must pass.

## 6. Frontend infrastructure (Amplify, Cognito, NextAuth)

- [ ] 6.1 In `infrastructure/stacks/amplify_construct.py`, add per-environment Vector hostnames (`dev.vector.sc0red.com`, `testing.vector.sc0red.com`, `vector.sc0red.com`) as Amplify branch domains. The old Janus hostnames stay configured (for the redirect step) but switch to redirect-mode.
- [ ] 6.2 Update Cognito allowed redirect URIs and logout URIs in `infrastructure/stacks/cognito_construct.py` to include the new hosts. Both old and new hosts SHALL be allowed during the 90-day cutover window.
- [ ] 6.3 Update CDK environment configs in `infrastructure/app.py` to read the new `FRONTEND_DOMAIN` (the Vector hostname) per environment. The variable name stays `FRONTEND_DOMAIN`; only the value changes.
- [ ] 6.4 Update NextAuth configuration in the frontend if it depends on a hardcoded host (search `frontend/src/` for `janus.sc0red.com` / `dev.janus.sc0red.com` literals).
- [ ] 6.5 ACM cert: ensure the new hosts are covered. If using a wildcard `*.vector.sc0red.com`, request and validate it. If using individual certs, add them to the Amplify domain config.

## 7. CSS / brand palette alignment

- [ ] 7.1 Compare `frontend/src/app/globals.css` (and any per-component overrides) against the sc0red.com tokens captured in 1.3. List divergences.
- [ ] 7.2 Update primary palette tokens (`--accent-blue`, `--accent-blue-glow`, etc.) where they materially diverge. Stay scoped to global CSS variables; do NOT restyle individual components.
- [ ] 7.3 Update typography tokens (font family, scale) if the company site uses different fonts — check `next/font` import in `layout.tsx`.
- [ ] 7.4 Visual smoke check across login page, dashboard, analysis detail, and the marketing landing page in both light and dark themes. Capture before/after screenshots in `visual/css-alignment/{before,after}/`.

## 8. Old-host redirect setup

- [ ] 8.1 Configure the old Janus Amplify domains (`dev.janus.sc0red.com` etc.) to serve HTTP 301 redirects to the matching Vector path. Verify with `curl -I -L` that the redirect chain resolves correctly to the new host's content.
- [ ] 8.2 Document the 90-day decommission window in `visual/notes.md` with a calendar reminder for the Janus host removal task.
- [ ] 8.3 Update the company website (separate repo, `sc0red.github.io/website-redux`) to link to the new Vector URL in the Vector Advisory product entry.

## 9. Tests, lint, type-check, architecture review

- [ ] 9.1 `cd frontend && npm run lint` — clean.
- [ ] 9.2 `cd frontend && npx tsc --noEmit` — clean.
- [ ] 9.3 `cd frontend && npm test` — all tests pass; section-order tests updated.
- [ ] 9.4 `cd backend && uv run ruff check src/` — clean.
- [ ] 9.5 `cd backend && uv run pytest tests/ -q` — all tests pass; coverage ≥ 95%.
- [ ] 9.6 `cd infrastructure && uv run cdk synth` — synth succeeds without diff that recreates AWS resources (this is the critical check that no resource rename leaked through). If `cdk diff` shows a Lambda / table / queue replace, STOP and find the rogue rename.
- [ ] 9.7 Run the architecture-reviewer agent on the change set. Resolve all CRITICAL findings; address or defer MEDIUM findings.

## 10. Visual verification (mirrors improve-pdf-export-content §7)

- [ ] 10.1 Pick three representative analyses (sparse / mid-size / deep EBITDA — same selection criteria as the PDF rebuild). Capture before-PDFs (current development state) and store under `openspec/changes/rename-janus-to-vector-advisory/visual/before/`.
- [ ] 10.2 After implementation, capture after-PDFs from the rebranded development environment. Store under `visual/after/`.
- [ ] 10.3 Page-by-page diff: confirm new section order, brand text, logo. Document any deviations in `visual/notes.md`.

## 11. Rollout

- [ ] 11.1 Open a PR against `development`. Include before/after screenshots in the PR description (sidebar brand, marketing page, analysis page section order, PDF cover).
- [ ] 11.2 Merge to `development`. Verify on `dev.vector.sc0red.com` (new) and `dev.janus.sc0red.com` (redirects to new). Soak 24h.
- [ ] 11.3 Open the `development → testing` promotion PR.
- [ ] 11.4 After testing soak, open the `testing → production` promotion PR.
- [ ] 11.5 Update sc0red.com company website to link to `vector.sc0red.com`.
- [ ] 11.6 Calendar a follow-up task 90 days post-production-cutover to decommission the old Janus hosts (Amplify domain config + Route 53 records).
- [ ] 11.7 Post-rollout: this change can archive at any time; it does not depend on `polished-pdf-export` or `improve-pdf-export-content` archive ordering, but its `polished-pdf-export` delta will resolve cleanly only after both prior PDF changes archive — note the dependency in the archive PR.
