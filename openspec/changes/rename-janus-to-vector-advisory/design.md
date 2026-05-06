## Context

The product was built and shipped as **Janus** — codename inherited from the early prototype, retained through the polished-pdf-export and improve-pdf-export-content launches. Leadership has now decided to publicly position the product as **Vector Advisory**, framed as an AI-augmented advisory companion for mid-market PE buyers and operators. The rename + reorder accompanies a broader sc0red company narrative ("AI tools + advisory for PE") visible on the company website (`https://sc0red.github.io/website-redux/`), which lists Vector Advisory alongside the separate **sc0red Platform** (an investor-focused product, different codebase).

Concurrent with the rename, the analysis page has been substantially restructured by PR #250 ("redesign detail page narrative ordering") — adding an executive strap, a strategy-map slot, and a deep-dive CTA. This proposal predates that work and originally described a section reorder against a flatter layout. The reorder portion is now Phase 3 below and is sequenced last because it should be designed against the current page, not against the page that existed when this proposal was first drafted.

The codebase has stabilised in the past few weeks: `polished-pdf-export`, `improve-pdf-export-content`, `light-theme-toggle`, and `dark-default-theme` have all archived (PRs #257 / #258); `webapp-ux-foundations-tier2` is also archived with §1 deferred; `ebitda-confidence-fields` shipped (PRs #260 / #261 / #262). The rebrand can proceed without conflicting with active work.

Constraints:
- Cannot break bookmarks for early users / leadership demos. A redirect from the old host to the new is required for at least one quarter (Phase 2).
- Cannot trigger AWS resource recreation (would require data migration, IAM updates, and downtime). Internal resource names stay `janus-*`.
- The repository remains `SC0RED/janus` (changing the GitHub repo name has cross-cutting consequences — Amplify GitHub PAT, branch protections, deploy workflows, etc.). The repo name is internal-facing for a solo-dev / small-team workflow; not customer-visible.
- Section-order changes (Phase 3) must be reflected consistently in the live analysis page AND the PDF export.

Stakeholders: leadership (positioning + Open Questions §1–§5, §7, §9), engineering (this proposal), early prospects (Phase 2 URL change + Phase 1/3 new-look UI).

## Goals / Non-Goals

**Goals:**

- The customer-facing product is unambiguously called *Vector Advisory* across UI text, page titles, email templates, alt text, and footer copy. (Phase 1)
- Customer-facing host is `vector.sc0red.com` (and per-environment variants); old Janus hosts continue to serve via redirect for at least 90 days post-launch. (Phase 2)
- The analysis page reads as an advisory walkthrough — leading with how the business works rather than with a risk score, the way an advisor would walk a client through their company. (Phase 3)
- The PDF export mirrors the new section order so on-screen and exported artifacts agree. (Phase 3)
- Visual styling (typography, palette, spacing) is recognisably part of the sc0red product family. (Phase 1)
- Zero AWS resource recreation. Zero data migration.
- Zero behavioural regression in non-rename surfaces — auth, scan flow, opportunities, EBITDA tree, value chain, PDF export all keep working unchanged.

**Non-Goals:**

- Renaming AWS resources (Lambdas, DynamoDB, SQS, IAM roles, log groups, Secrets Manager paths, dashboards). All stay `janus-*`.
- Renaming the GitHub repository, internal Python / Node packages (`janus-backend`, `janus-frontend`), CDK stacks (`Janus-{env}`), Docker container names, or local dev DynamoDB table.
- Generating strategy maps or any new AI capability — that's `ai-strategy-map`.
- Changing the analysis pipeline output schema (no new fields, no removed fields).
- Changing the PDF export pipeline (Puppeteer Lambda, signed-token flow, Cognito gate stay as-is).
- Reworking the analysis page beyond the section reorder + brand text. No new components, no UX rework of existing components.
- Per-section page-format overrides in the PDF beyond what `improve-pdf-export-content` already established.
- Any CSS rewrite — palette / token *adjustment* only, not a redesign.
- Cognito User Pool migration (Open Question §4 must answer "acceptable" for the rebrand to proceed in its current scope).

## Decisions

### 0. Split into three phases

**Decision**: The originally bundled rebrand is split into three sequential phases, each shippable as a separate PR with its own rollback story:

```
Phase 1 — vector-advisory-brand-text
  • Brand text, logo, page titles, email, marketing page,
    CSS palette / typography tokens, README + CLAUDE.md
  • No infra change; lives on existing Janus host
  • Reversible via git revert
  • Blocked on Open Questions §1, §2, §3, §7, §8

         ↓ ships, soaks on dev.janus.sc0red.com

Phase 2 — vector-advisory-host-cutover
  • Amplify per-env hosts, ACM cert, Cognito redirects,
    NextAuth callback, 301 redirect from old hosts
  • Live-infra change; carries auth-flow risk
  • Reversible: swap Amplify domain back; brand text unaffected
  • Blocked on Open Questions §4, §6, §10

         ↓ ships independently of Phase 3

Phase 3 — analysis-page-advisory-reorder
  • AnalysisDetail.tsx + PrintReport.tsx section reorder
  • Independent of brand work; orthogonal scope
  • Reversible via git revert
  • Blocked on Open Question §9 (the reorder itself —
    the world has moved since this proposal was first drafted)
```

**Why split:**

| Reason | Detail |
|---|---|
| Risk isolation | Phase 2 is the only one that can break login. Phase 1 cannot. Phase 3 cannot. Bundling Phase 2 with Phase 1 means a Cognito misconfiguration takes the whole rebrand down. |
| Independent blockers | Phase 1 needs leadership copy (§1, §2, §3); Phase 2 needs host confirmation (§4, §6, §10); Phase 3 needs reorder direction (§9). Bundling forces the slowest blocker to gate everything. |
| Independent rollback | Each phase has its own revert path. A bundled PR forces an all-or-nothing revert decision when only one of three sub-changes broke. |
| Soak windows | Brand text changes can soak on the live janus host for days before host cutover, so confidence is high before customers start hitting the new URL. Bundled = no soak. |
| Re-thinking against current reality | Phase 3's reorder direction needs fresh design review against PR #250's layout. Splitting it out gives that design review its own change without holding up Phases 1 / 2. |

**Why not split into four (lifting CSS palette to its own change)**: Phase 1 is already small; CSS is a token-level audit (~10 changes); a fourth split is admin overhead with no risk-isolation benefit.

**Trade-off accepted**: three sequential PRs is more meta-work than one PR. Justified by risk isolation and the fact that the open-question dependencies are different per phase.

**Implementation note**: For the OpenSpec workflow, the simplest path is to keep ONE change folder (`rename-janus-to-vector-advisory/`) with three phase-tagged task groups in `tasks.md`. Each phase ships as a separate PR but all share one proposal/design until archive. If a phase's scope balloons during apply, it can split into its own OpenSpec change at that point.

### 1. Customer-visible only — internal `janus-*` resource names stay

**Decision**: Customer-visible surfaces (URL, brand text, logo, page titles, emails) flip to Vector Advisory. AWS resources, CDK stack names, internal package names, repository name, and Docker containers keep `janus-*` everywhere they exist today.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Full rename including AWS resources | Renaming a DynamoDB table requires data migration + IAM policy churn + downtime. Renaming SQS queues breaks in-flight messages. Renaming Lambda functions changes ARNs that other components reference. All of this for zero customer value. |
| Rename only the repository and CDK stack, keep resource names | Pointless half-measure: every developer would still see `janus_stack.py` produces `vector-{env}` resources, which is just confusion. Either fully rename or keep clean. |
| Defer the rename until a "real" architectural rename window | Blocks the leadership positioning bet behind future infra work that may never happen. |

**Trade-off**: A new dev opening the codebase will see "janus" everywhere internally and "Vector Advisory" externally. This is a real onboarding wrinkle. Mitigation: Phase 1 task adds a clear note in `CLAUDE.md` and `README.md` ("Vector Advisory is the customer-facing product name; resources are named `janus-*` for historical reasons — this is intentional and not a TODO").

**See Open Question §4** for the visible-Cognito edge: forgot-password / MFA / OAuth-consent screens rendered by Cognito display the User Pool's app name, which stays `janus-*`. This is the most user-visible consequence of the "internal-only" decision and needs leadership sign-off.

### 2. Old Janus host: 301-redirect, not decommission

**Decision**: For at least 90 days after Vector Advisory launches (Phase 2), `dev.janus.sc0red.com` (and equivalents) returns HTTP 301 redirects to `vector.sc0red.com` for the matching path. After 90 days, the old host can be decommissioned; remove the Route 53 record.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Decommission immediately at launch | Breaks every internal bookmark, every email link in the wild, every deck slide that screenshots the URL. Avoidable pain. |
| Keep redirect indefinitely | Long tail of stale URLs in search engines / docs. After 90 days the cost of the redirect (DNS + cert) outweighs its value. |
| Display a "we've moved" banner instead of redirect | Worse UX than a clean redirect; the user has to click again. |

**Trade-off**: 90-day window means the launch isn't fully clean for a quarter. Acceptable cost for not-breaking-things. **See Open Question §10 for confirmation.**

### 3. Per-environment hostname pattern

**Decision (proposed, awaiting confirmation per Open Question §6)**: Three customer hosts, one per environment:

- Development: `dev.vector.sc0red.com`
- Testing: `testing.vector.sc0red.com`
- Production: `vector.sc0red.com`

The sub-subdomain pattern keeps environments visually distinct (a developer landing on `dev.vector.sc0red.com` knows they're not on prod) and matches the existing convention (`dev.janus.sc0red.com`).

**Alternatives considered:**

- `vector-dev.sc0red.com` / `vector-testing.sc0red.com` / `vector.sc0red.com` — flat at the same level. Less convention-following; production looks like the parent of the others, which is misleading.
- Promotion-based aliasing (`vector.sc0red.com` always points to the latest stable) — too clever, breaks intuition for non-prod testing.

**Trade-off**: ACM cert needs to cover three hostnames or a wildcard `*.vector.sc0red.com`. Minor cost. Recommend wildcard.

### 4. Brand text strategy — search + replace, with curation

**Decision**: Treat the rename as primarily a string substitution (`Janus` → `Vector Advisory` in customer-visible contexts), but explicitly curate the high-stakes copy: page titles, login / signup brand block, marketing landing page tagline, email templates. Bulk replacement of incidental mentions; hand-curate the headline strings.

**Implication for Phase 1 work**: tasks split into "automated find-and-replace pass" (covered by `tasks.md` Phase 1 §2) and "hand-edit headline copy" (Phase 1 §3). The hand-edit list is small (under 10 strings); the bulk pass covers the long tail.

**Trade-off**: Finding-and-replacing risks accidentally changing strings that should stay (e.g., "JanusStack" the CDK class). Mitigation: the substitution scope is restricted to specific file types and excludes infrastructure files. Phase 1 tasks document the exact glob.

### 5. Section reorder anchored to advisory reading flow (Phase 3 — needs re-thinking)

**Decision**: Phase 3 designs a section reorder against the *current* analysis-page layout (post-PR #250), not against the layout assumed when this proposal was first drafted. The original proposed order ("Value Chain → EBITDA → Risk + Opportunities") may still be the right call, but the surrounding sections (executive strap, strategy map, deep-dive CTA) didn't exist when the proposal was written and the design needs to be re-validated.

**Current canonical layout (per `analysis-detail-narrative` spec, post-PR #250):**

```
1. AnalysisHeader
2. AnalysisExecutiveStrap                  ← added in #250
3. AnalysisOverviewCards
4. TopActionsCallout
5. StrategyMap (when present)              ← added in #250
6. DeepDiveCTA (when StrategyMap present)  ← added in #250
7. EbitdaSection
8. ValueChainDiagram
9. RiskBreakdown
10. ValueLeverSummary
11. OpportunitiesList
```

**Original proposal's intended reorder** (from this design doc's earlier draft):

```
1. AnalysisHeader
2. AnalysisOverviewCards
3. TopActionsCallout
4. ValueChainDiagram      ← MOVED UP from old position 7
5. EbitdaSection          ← MOVED UP from old position 11
6. RiskBreakdown          ← MOVED DOWN from old position 4
7. ValueLeverSummary + OpportunitiesList + Sc0redCTABanner
8. Re-analysis + DocumentUpload (interactive footer)
```

**The two are not the same.** Phase 3's design pass needs leadership input on whether the new layout (with executive strap + strategy map + deep-dive CTA at the top) should *also* swap the EBITDA and ValueChain positions, or whether the current order is good enough now that the strategy-map sits at the top of the page and frames everything below it. **See Open Question §9.**

**Original rationale (still applies)**: The advisory narrative reads: "Here's the company → here's an at-a-glance score → here are the immediate plays → here's how the business actually works → here's where AI moves the financial outcome → here are the specific risks and opportunities to act on → upload more documents to refine."

### 6. PDF mirrors screen order (Phase 3)

**Decision**: `PrintReport.tsx` reorders to match whatever Phase 3 settles on. **Whether** to reorder depends on the answer to Open Question §9. The polished-pdf-export delta in `specs/polished-pdf-export/spec.md` documents the *original* proposed order; if §9 settles on a different order, the delta needs updating before Phase 3 ships.

The polished-pdf-export capability spec gets a delta to update the section-order requirement.

### 7. CSS / brand alignment is a curated audit, not a redesign

**Decision**: A focused review of the sc0red.com design language — primary palette, typography, spacing scale, accent treatment — and adjustment of design tokens in Janus's CSS where they diverge from the company site. Specifically NOT a component-by-component restyle. The audit produces a small list of token changes; if it grows beyond ~10 token adjustments, scope spills into a separate change.

**Why this scope**: a full visual rework is a multi-week project; a token-level alignment is days. Goal here is "looks like family," not "perfect visual harmony."

**Blocked on Open Question §8** (Figma source vs visual audit).

### 8. Logo asset replacement

**Decision**: `frontend/public/janus-logo.png` is replaced by a `vector-advisory-logo.png` (or `vector-logo.svg` if we get a vector asset from design). Five components reference the file via `<img src="/janus-logo.png" alt="Janus">` — all are updated to the new path + alt text. The old PNG can be deleted post-cutover.

**Blocked on Open Question §3** (asset existence). Fallback: ship typographic-only wordmark for v1 and add the icon later as a small follow-up commit.

**Trade-off**: Cache busting — if any user has the old logo cached, they'll see it for a session. Acceptable; the page reload picks up the new file.

## Risks / Trade-offs

- **[Phase 1 Risk]** Find-and-replace catches strings that should NOT change (e.g., commit messages quoting old logs, fixture data, error messages from before the rename).
  → **Mitigation**: substitution scope explicitly restricted in `tasks.md`; excludes `infrastructure/`, `backend/scripts/`, `backend/tests/`, all `.test.ts*` files, lock files, and `cdk.out/`. The hand-curated step covers the high-stakes copy directly.
- **[Phase 2 Risk]** Cognito redirect URI / NextAuth callback config not updated in time, breaks login on the new host.
  → **Mitigation**: Phase 2 tasks gate the host cutover behind a verified Cognito allowlist update + a smoke-test login on a preview build.
- **[Phase 3 Risk]** PDF export rendering breaks because the section order change interacts badly with `print-section--break-before` rules.
  → **Mitigation**: Phase 3 re-runs the visual verification gate from `improve-pdf-export-content` (capture before/after on three representative analyses).
- **[Phase 1+2 Risk]** Old host still serves the new code with the new brand, creating a confusing duplicate during the dual-serve window.
  → **Mitigation**: Phase 2 cutover plan — Amplify Janus host is set to 301 redirect to Vector host *before* the Phase 1 brand goes live on the new host, eliminating the duplicate-serving window.
- **[Phase 2 Risk]** SEO impact from URL change. Search engines need time to re-index `vector.sc0red.com`; internal links from social / docs may still hit the old URL.
  → **Mitigation**: 301 redirects preserve PageRank. Update internal docs, GitHub README, the company-site link from sc0red.com → Vector. Submit an updated sitemap to Google Search Console.
- **[Cross-phase risk]** Internal cognitive friction — devs have to remember "we say Vector publicly but the code says janus." Onboarding cost.
  → **Mitigation**: a single-paragraph note in `CLAUDE.md` + `README.md` explaining the convention (Phase 1).
- **[Phase 3 Risk]** The reorder regresses the existing PDF-export visual verification (we shipped that recently).
  → **Mitigation**: re-run the visual verification gate as part of Phase 3 rollout. Reuses the existing `mint-print-url.mjs` script.
- **[Phase 1 Risk]** Brand assets are missing — we don't yet have a finalised Vector Advisory logo file.
  → **Mitigation**: Open Question §3 + Phase 1's first task is a "logo handoff" gate; if the asset isn't ready by implementation, ship with a typographic-only treatment and add the icon when available.
- **[Cross-phase risk]** The repo name `SC0RED/janus` is visible in PR URLs / git remote / CI logs / issue links. Not changing it means external observers see "janus" anyway.
  → **Mitigation**: accept this (Open Question §5). Repo rename is a separate, larger change with its own ripple effects (Amplify GitHub PAT, deploy keys, branch protections). Worth doing later as a clean follow-up if external visibility becomes a real concern.
- **[Phase 2 Risk]** Cognito-rendered pages (forgot password, MFA challenge, OAuth consent) display the User Pool's app name, which stays `janus-*`. Customer-visible split-brain.
  → **Mitigation**: Open Question §4 must answer "acceptable" for this proposal to proceed. If "not acceptable," scope expands to a Cognito User Pool migration (separate change).

## Migration Plan

This is a customer-visible rename, so launch order matters. Each phase has its own internal launch sequence; the phases themselves run sequentially:

```
Phase 1 — vector-advisory-brand-text
  Step 1.1: Land brand-text PR on `development`. App still serves
            from dev.janus.sc0red.com but the page renders Vector
            Advisory branding. No infra change.
  Step 1.2: Soak 24h. Verify all login + scan + analysis flows
            still work.
  Step 1.3: Promote to testing → soak → promote to production.

Phase 2 — vector-advisory-host-cutover
  Step 2.1: Add Vector Amplify domains + ACM cert + Cognito
            redirect URI allowlist (both old and new). Land on
            `development`. Vector host now serves alongside Janus
            host; both work.
  Step 2.2: Verify on dev.vector.sc0red.com that login + scan +
            analysis + PDF export all work. dev.janus.sc0red.com
            keeps serving.
  Step 2.3: Cutover gate — switch the OLD dev.janus.sc0red.com
            Amplify domain to 301-redirect to dev.vector.sc0red.com.
            Verify with curl + browser.
  Step 2.4: Document propagation — update sc0red.com company website
            to link to the new URL. Update README, CLAUDE.md.
  Step 2.5: Promote to testing → soak → promote to production.
  Step 2.6: 90 days post-production-cutover, decommission old
            Janus hosts (Amplify domain config + Route 53 records).

Phase 3 — analysis-page-advisory-reorder
  Step 3.1: Design the reorder against the current layout (post-#250).
  Step 3.2: Land reorder PR on `development`. Sub-component renders
            unchanged; only JSX position shifts.
  Step 3.3: Verify both on-screen and PDF render correctly.
  Step 3.4: Promote to testing → soak → promote to production.

Phases 1 and 3 are independent and CAN ship in either order;
Phase 2 SHOULD ship after Phase 1 so the Janus host is already
showing the new brand when its domain redirects to the Vector URL
(consistent rebrand experience during the redirect chain).
```

**Rollback strategy** (per phase):

- Phase 1: `git revert <PR>` on the brand-text commit. Page reverts to "Janus" instantly.
- Phase 2: swap the Amplify domain config back so `dev.janus.sc0red.com` serves the codebase directly. Revert Cognito redirect URI removal (keep both allowlists). Vector host stays available for users who already migrated.
- Phase 3: `git revert <PR>` on the reorder commit. Page reverts to the post-PR-#250 order.

## Open Questions (deferred to leadership)

The proposal-level "Open Questions for Leadership" section in `proposal.md` is the canonical list. Those questions block apply per the table in the proposal. Briefly summarized here for design-doc context:

| # | Question | Phase blocked |
|---|---|---|
| 1 | Final product name (Vector Advisory vs Vector?) | Phase 1, Phase 2 |
| 2 | Tagline (placeholder: "AI Risk & Strategic Intelligence") | Phase 1 |
| 3 | Logo asset availability | Phase 1 |
| 4 | Cognito User Pool brand visibility (split-brain acceptable?) | Phase 2 |
| 5 | Repository name visibility (acceptable to keep `SC0RED/janus`?) | Phase 1 (advisory) |
| 6 | Per-environment hostname pattern confirmation | Phase 2 |
| 7 | Email "from" sender display name | Phase 1 |
| 8 | CSS palette source of truth (Figma vs visual audit) | Phase 1 |
| 9 | Section reorder direction against current layout | Phase 3 |
| 10 | 90-day dual-serve window confirmation | Phase 2 |
