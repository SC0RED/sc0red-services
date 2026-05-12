## Status

**This proposal has been restructured into a three-phase split (see "What Changes" below) and is blocked on leadership input. Do NOT run `/opsx:apply` until at least Open Questions §1–§5 are answered.**

## Open Questions for Leadership

The proposal cannot land any code until the following are settled. Each is annotated with which phase it blocks.

| # | Question | Why it matters | Blocks |
|---|---|---|---|
| **1** | Final product name — **"Vector Advisory"** or **"Vector"**? | Every brand string in the codebase, every page title, every email, the logo wordmark, the Cognito redirect URL, the marketing landing page. A late name change is a second cycle of every step. | Phase 1, Phase 2 |
| **2** | Tagline — placeholder is **"AI Risk & Strategic Intelligence."** What's the final? | Page titles (`<title>` element), browser tab text, marketing hero, OG / Twitter card meta tags. Settles within Phase 1. | Phase 1 |
| **3** | Logo asset — does a finalised **`vector-advisory-logo.png` / `.svg`** exist, or do we ship a typographic-only wordmark for v1? | Five `<img src>` references need to swap, including the cover page of the PDF export. If we ship typographic-only, design can hand off the asset later as a small follow-up. | Phase 1 |
| **4** | Cognito User Pool brand visibility — the User Pool keeps `janus-*` naming. Forgot-password flows, MFA challenges, and any OAuth consent screen rendered by Cognito display **"Janus"** as the app name. Acceptable for the rebrand launch? | If "no, this must say Vector Advisory," the scope expands materially: Cognito User Pool migration (= losing all users or doing a cross-pool migration with manual sign-in coordination). Currently the proposal accepts the split-brain. | Phase 2 |
| **5** | Repository name `SC0RED/janus` stays — visible in PR URLs, issue links, status pages, and any deck slide that shows a repo URL. Acceptable, or does the rebrand launch require a repo rename? | Repo rename has cross-cutting consequences (Amplify GitHub PAT regeneration, deploy keys, branch protections, every URL in CI logs). Currently the proposal accepts that "janus" is internally visible. | Phase 1 (but not strictly blocking — could ship rebrand and rename repo as a separate later change) |
| 6 | Per-environment hostname pattern — proposal says **`dev.vector.sc0red.com`** / **`testing.vector.sc0red.com`** / **`vector.sc0red.com`**. Confirm or substitute. | Drives Amplify domain config + ACM cert SANs (or wildcard) + Cognito allowed redirect URIs in Phase 2. | Phase 2 |
| 7 | Email "from" sender display name — invitation emails currently say **"Janus by SignalField"**. Does the rebrand also update the sender display name and the technical `from:` address? | If yes, scope expands to SES configuration / Cognito email templates and possibly DKIM / SPF re-validation. If no, the email body says "Vector Advisory" but the sender chip says "Janus" — visible mismatch. | Phase 1 |
| 8 | CSS palette — is sc0red.com's design language captured in a **Figma file or brand guide** we can read tokens from, or do we audit visually? | Figma → can extract exact tokens; visual audit → approximate match. The "alignment, not redesign" scope only holds if we have a small, concrete list of token changes. | Phase 1 |
| 9 | Section reorder direction — PR #250 already shipped a reorder ([analysis-detail-narrative spec](../../specs/analysis-detail-narrative/spec.md)) with **EBITDA at #7, Value Chain at #8**. This proposal originally wanted **Value Chain at #4, EBITDA at #5** with everything else shifted. Given the world has moved, what's the right reorder against today's layout? | Phase 3's exact scope. The decision to swap EBITDA ↔ Value Chain and demote Risk vs leaving the current order is leadership's call about the advisory-narrative framing. | Phase 3 |
| 10 | 90-day dual-serve window — both old (`*.janus.sc0red.com`) and new (`*.vector.sc0red.com`) hosts serve simultaneously for ~3 months, with the old ones 301-redirecting after cutover. Confirm or shorten. | Affects Amplify domain configuration and the cost / risk of running double infrastructure. | Phase 2 |

## Why

The product currently shipped as **Janus** is being repositioned as **Vector Advisory** at `vector.sc0red.com` to align with sc0red's company narrative — "AI tools + advisory for mid-market PE." The rename is a positioning bet: "Janus" is mythological and gives no clue what the product does; "Vector Advisory" is directional, signals strategic intent, and frames the product as an advisory companion rather than a risk-score generator. CSS / brand alignment with `sc0red.com` makes Vector Advisory feel like a member of the sc0red product family rather than a one-off tool.

This change is **customer-visible only**. Internal infrastructure (Lambda names, DynamoDB table, SQS queues, IAM resource names) keeps the `janus-*` naming because renaming infra resources would require risky data migrations for zero customer value. The brand is the wrapper; the wiring stays. Leadership has accepted this split — see Open Question §4 for the consequence on Cognito-rendered pages.

## What Changes

The original single proposal bundled four concerns: (A) brand text + assets, (B) host cutover, (C) section reorder, (D) CSS palette alignment. They have very different risk profiles (host cutover can break login; brand text cannot) and different blocking dependencies (brand text needs leadership copy; host cutover needs the hosts confirmed; reorder is independent). Bundling them makes review harder, rollback messier, and forces every phase to wait for every other phase's blocker.

**Restructured into three phases, each shippable as its own PR:**

### Phase 1 — `vector-advisory-brand-text`
*Customer-facing brand on the existing Janus host. Reversible. Low risk.*

- Page titles, marketing landing page, sidebar, login / signup / oauth-authorize / accept-invite pages
- Logo asset replacement (or typographic wordmark fallback per Open Question §3)
- Email template (`backend/src/handlers/templates/invitation_email.html`)
- Settings copy, `useTheme.ts` docstring
- `CLAUDE.md` + `README.md` retitle + naming-convention paragraph
- CSS palette / typography token alignment with sc0red.com (token-level, ~10 changes max)

After Phase 1: dev.janus.sc0red.com still serves but the page renders the Vector Advisory brand. Soak window. No infra change. **Rollback = git revert of the brand-text PR.**

### Phase 2 — `vector-advisory-host-cutover`
*Live-infrastructure change. Risky. Sequenced after Phase 1.*

- Amplify domain config: add `dev.vector.sc0red.com` / `testing.vector.sc0red.com` / `vector.sc0red.com`
- ACM cert: wildcard `*.vector.sc0red.com` or per-host SANs
- Cognito allowed redirect URIs + logout URIs (Open Question §6)
- NextAuth callback URL config follows the new hosts
- 301 redirect from `*.janus.sc0red.com` → `*.vector.sc0red.com` (90-day window per Open Question §10)
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

- `vector-advisory-branding` (Phase 1 + Phase 2): customer-facing brand requirements — product name, brand asset usage, email-template branding, customer-facing host. The current spec at `specs/vector-advisory-branding/spec.md` covers Phase 1 + Phase 2 jointly; will be split if the apply work splits into separate OpenSpec changes.

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
