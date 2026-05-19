## Status

**Phase 1 unblocked — ready to ship.** Christopher Creel confirmed the brand name (sc0red Advisory), the logo source (development.sc0red.com), and the visual reference (development.sc0red.com) on 2026-05-19. Tagline stays as the current placeholder. Email sender display unchanged.

**Phase 2 and Phase 3 remain blocked** on the remaining open questions (§4, §6, §9, §10). They are documented future work; this change ships Phase 1 first and revisits Phase 2/3 when leadership is ready.

## Open Questions for Leadership

| # | Question | Status | Blocks |
|---|---|---|---|
| **1** | Final product name? | ✅ **ANSWERED: sc0red Advisory** (Christopher Creel, 2026-05-19) | — |
| **2** | Tagline | ✅ **ANSWERED: keep current placeholder** "AI Risk & Strategic Intelligence" — can revisit later as a copy-only PR | — |
| **3** | Logo asset | ✅ **ANSWERED: extract from development.sc0red.com** (Christopher Creel, 2026-05-19). Pull the published logo asset off that site and add it to `frontend/public/`. | — |
| **4** | Cognito User Pool brand visibility — keeps `janus-*` naming; forgot-password / MFA / OAuth consent rendered by Cognito will display "Janus". Acceptable for the rebrand launch? | 🟡 **DEFERRED to Phase 2.** Mitigated for the partner demo because Janus uses NextAuth + `USER_PASSWORD_AUTH`, so login / signup / forgot-password are rendered by our React app, not Cognito's hosted UI. Cognito-hosted screens are only reached on OAuth-consent / MFA flows, which aren't part of the demo path. | Phase 2 |
| **5** | Repo name `SC0RED/janus` stays. Acceptable, or rename? | 🟡 **DEFERRED.** No customer surface; punt to a separate later change if desired. | Out of scope |
| 6 | Per-environment hostname pattern — `dev.advisory.sc0red.com` / `testing.advisory.sc0red.com` / `advisory.sc0red.com`. Confirm or substitute. | 🟡 **DEFERRED to Phase 2.** Placeholder retained in the spec; substitute at Phase 2 design time. | Phase 2 |
| 7 | Email "from" sender display name. | ✅ **ANSWERED: keep "Janus by SignalField" as-is for now.** No SES configuration / DKIM / SPF re-validation needed. Email body brand still flips to sc0red Advisory in Phase 1 — the sender chip becomes a known visible mismatch, accepted for now. Re-revisit when Cognito User Pool work happens (Phase 2). | — |
| 8 | CSS palette source | ✅ **ANSWERED: development.sc0red.com is the visual reference.** Token-level visual audit, not pixel-aligned. | — |
| 9 | Section reorder direction (Phase 3) | 🟡 **DEFERRED.** Phase 3 is independent of brand work and not required for the partner demo. | Phase 3 |
| 10 | 90-day dual-serve window | 🟡 **DEFERRED to Phase 2.** | Phase 2 |

**Trigger for revisiting Phase 2:** the partner demo runs on `dev.janus.sc0red.com` with the new brand chrome. If leadership wants the URL itself to read sc0red Advisory after the demo, Phase 2 work resumes with §4, §6, §10 to answer.

## Why

The product currently shipped as **Janus** is being repositioned as **sc0red Advisory** at `advisory.sc0red.com` to align with sc0red's company narrative — "AI tools + advisory for mid-market PE." The rename is a positioning bet: "Janus" is mythological and gives no clue what the product does; "sc0red Advisory" is directional, signals strategic intent, and frames the product as an advisory companion rather than a risk-score generator. CSS / brand alignment with `sc0red.com` makes sc0red Advisory feel like a member of the sc0red product family rather than a one-off tool.

This change is **customer-visible only**. Internal infrastructure (Lambda names, DynamoDB table, SQS queues, IAM resource names) keeps the `janus-*` naming because renaming infra resources would require risky data migrations for zero customer value. The brand is the wrapper; the wiring stays. Leadership has accepted this split — see Open Question §4 for the consequence on Cognito-rendered pages.

## What Changes

The original single proposal bundled four concerns: (A) brand text + assets, (B) host cutover, (C) section reorder, (D) CSS palette alignment. They have very different risk profiles (host cutover can break login; brand text cannot) and different blocking dependencies (brand text needs leadership copy; host cutover needs the hosts confirmed; reorder is independent). Bundling them makes review harder, rollback messier, and forces every phase to wait for every other phase's blocker.

**Restructured into three phases, each shippable as its own PR:**

### Phase 1 — `sc0red-advisory-brand-text`
*Customer-facing brand on the existing Janus host. Reversible. Low risk.*

- Page titles, marketing landing page, sidebar, login / signup / oauth-authorize / accept-invite pages
- Logo asset replacement (or typographic wordmark fallback per Open Question §3)
- Email template (`backend/src/handlers/templates/invitation_email.html`)
- Settings copy, `useTheme.ts` docstring
- `CLAUDE.md` + `README.md` retitle + naming-convention paragraph
- CSS palette / typography token alignment with sc0red.com (token-level, ~10 changes max)

After Phase 1: dev.janus.sc0red.com still serves but the page renders the sc0red Advisory brand. Soak window. No infra change. **Rollback = git revert of the brand-text PR.**

### Phase 2 — `sc0red-advisory-host-cutover`
*Live-infrastructure change. Risky. Sequenced after Phase 1.*

- Amplify domain config: add `dev.advisory.sc0red.com` / `testing.advisory.sc0red.com` / `advisory.sc0red.com`
- ACM cert: wildcard `*.advisory.sc0red.com` or per-host SANs
- Cognito allowed redirect URIs + logout URIs (Open Question §6)
- NextAuth callback URL config follows the new hosts
- 301 redirect from `*.janus.sc0red.com` → `*.advisory.sc0red.com` (90-day window per Open Question §10)
- CDK env config: `FRONTEND_DOMAIN` per environment

After Phase 2: customers can reach the app at the new host; old host redirects. **Rollback = revert the Amplify domain swap so old host serves directly again. Brand text on the page is independent — does not need to revert.**

### Phase 3 — `analysis-page-advisory-reorder`
*Independent of brand work. Section ordering decision against today's layout (post-PR #250). Reversible.*

- `AnalysisDetail.tsx` — reorder JSX below TopActionsCallout
- `PrintReport.tsx` — mirror the reorder
- Vitest assertions on rendered DOM order
- The `analysis-detail-narrative` canonical spec gets an updated "Section ordering" requirement

**Note on the world having moved:** when this proposal was first drafted, the analysis page was a flat list. PR #250 has since shipped a curated narrative order with executive strap, strategy map, and deep-dive CTA. The proposal's *original* reorder ("Value Chain → EBITDA → Risk + Opportunities") needs a fresh decision against the current layout — see Open Question §9.

### What is NOT changing (any phase)

- Repository name (`SC0RED/janus` stays — see Open Question §5)
- Internal Python / Node package names (`janus-backend`, `janus-frontend`)
- CDK stack names (`Janus-development`, `Janus-staging`, `Janus-production`)
- AWS resource names (Lambda, DynamoDB, SQS, IAM, log groups, Secrets Manager paths, dashboards)
- Docker container names, dev DynamoDB table (`janus-dev`)
- Test fixtures, internal docstrings that don't surface to customers

## Capabilities

### New Capabilities

- `sc0red-advisory-branding` (Phase 1 + Phase 2): customer-facing brand requirements — product name, brand asset usage, email-template branding, customer-facing host. The current spec at `specs/sc0red-advisory-branding/spec.md` covers Phase 1 + Phase 2 jointly; will be split if the apply work splits into separate OpenSpec changes.

### Modified Capabilities

- `polished-pdf-export` (Phase 1 + Phase 3): brand text in the cover, footer, and methodology block (Phase 1); section ordering in the rendered PDF (Phase 3). The current delta at `specs/polished-pdf-export/spec.md` covers both; will be split if needed.
- `analysis-detail-narrative` (Phase 3): section ordering requirement updated to reflect the post-PR-#250 layout with the advisory-narrative reorder applied. **This delta does NOT exist in the current artifact and will be added in Phase 3 once Open Question §9 is resolved.**

## Impact

- **Frontend** (Phase 1: ~10–15 files; Phase 3: 2 files): every page that renders the brand string, logo, alt text, or page title.
- **Backend** (Phase 1: 1 file): `invitation_email.html` brand text + footer.
- **Infrastructure** (Phase 2: 2–3 files): `infrastructure/stacks/amplify_construct.py`, `infrastructure/stacks/cognito_construct.py`, `infrastructure/app.py`.
- **DNS / CDN** (Phase 2): three new Route 53 records (or Amplify-managed equivalents); the existing Janus hosts keep serving with a 301 redirect for ~90 days post-cutover.
- **Auth / Cognito** (Phase 2): redirect URIs and allowed origins on the Cognito app client need to include the new hosts. NextAuth callback URL config follows.
- **Tests**: Playwright E2E setup files reference `dev.janus.sc0red.com` host (Phase 2). Unit tests using "Janus" in fixtures / mock brand strings updated where the assertion is on customer-visible text (Phase 1). No internal-fixture renames.
- **CI / deploy workflows** (Phase 2): variables referencing `FRONTEND_DOMAIN` or hardcoded host strings checked; CDK env config updated per environment.
- **Documentation** (Phase 1): README, public-facing docs, marketing landing page copy. Internal architecture docs that describe codebase structure keep "janus" where they reference resource names that aren't being changed.
- **Observability** (Phase 2): any CloudWatch log queries, metric filters, or dashboards saved by hostname adjusted. Resource-name-based filters unchanged.
- **Out of scope** (any phase): AI strategy map generation (separate change `ai-strategy-map`), Cognito User Pool migration (Open Question §4 must answer "acceptable" for this proposal to proceed without a major-scope expansion).
