## Context

The product was built and shipped as **Janus** — codename inherited from the early prototype, retained through the polished-pdf-export and improve-pdf-export-content launches. Leadership has now decided to publicly position the product as **Vector Advisory**, framed as an AI-augmented advisory companion for mid-market PE buyers and operators. The rename + reorder accompanies a broader sc0red company narrative ("AI tools + advisory for PE") visible on the company website (`https://sc0red.github.io/website-redux/`), which lists Vector Advisory alongside the separate **sc0red Platform** (an investor-focused product, different codebase).

Concurrent with the rename, leadership is also commissioning a **strategy-map generation feature** that will sit at the top of the analysis page and drive a "Contact us for deep dive" conversion path. That feature is being scoped as a separate OpenSpec change (`ai-strategy-map`); it is explicitly out of scope here. This proposal handles only the rename + section reorder + branding alignment so that change can ship fast and unblock the strategy-map work.

The codebase is mid-flight on several other in-progress changes (`improve-pdf-export-content` shipped last week, `polished-pdf-export` not yet archived, `dark-default-theme` post-rollout, `webapp-ux-foundations-tier2` in flight). The rename has to navigate around active work without conflicting.

Constraints:
- Cannot break bookmarks for early users / leadership demos. A redirect from the old host to the new is required for at least one quarter.
- Cannot trigger AWS resource recreation (would require data migration, IAM updates, and downtime). Internal resource names stay `janus-*`.
- The repository remains `SC0RED/janus` (changing the GitHub repo name has cross-cutting consequences — Amplify GitHub PAT, branch protections, deploy workflows, etc.). The repo name is internal-facing for a solo dev / small-team workflow; not customer-visible.
- Section-order changes must be reflected consistently in the live analysis page AND the PDF export, which we just rebuilt.

Stakeholders: leadership (positioning), the leader bringing strategic-framework expertise (handing off white papers to the next change), engineering (this PR), early prospects (URL change + new-look UI).

## Goals / Non-Goals

**Goals:**
- The customer-facing product is unambiguously called *Vector Advisory* across UI text, page titles, email templates, alt text, and footer copy.
- Customer-facing host is `vector.sc0red.com` (and per-environment variants); old Janus hosts continue to serve via redirect for at least 90 days post-launch.
- The analysis page reads as an advisory walkthrough — value chain → EBITDA → risk + opportunities — instead of an analyst-tool dashboard that leads with a risk score.
- The PDF export mirrors the new section order so on-screen and exported artifacts agree.
- Visual styling (typography, palette, spacing) is recognisably part of the sc0red product family.
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

## Decisions

### 1. Customer-visible only — internal `janus-*` resource names stay

**Decision**: Customer-visible surfaces (URL, brand text, logo, page titles, emails) flip to Vector Advisory. AWS resources, CDK stack names, internal package names, repository name, and Docker containers keep `janus-*` everywhere they exist today.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Full rename including AWS resources | Renaming a DynamoDB table requires data migration + IAM policy churn + downtime. Renaming SQS queues breaks in-flight messages. Renaming Lambda functions changes ARNs that other components reference. All of this for zero customer value. |
| Rename only the repository and CDK stack, keep resource names | Pointless half-measure: every developer would still see `janus_stack.py` produces `vector-{env}` resources, which is just confusion. Either fully rename or keep clean. |
| Defer the rename until a "real" architectural rename window | Blocks the leadership positioning bet behind future infra work that may never happen. |

**Trade-off**: A new dev opening the codebase will see "janus" everywhere internally and "Vector Advisory" externally. This is a real onboarding wrinkle. Mitigation: a clear note in `CLAUDE.md` and `README.md` ("Vector Advisory is the customer-facing product name; resources are named `janus-*` for historical reasons — this is intentional and not a TODO").

### 2. Old Janus host: 301-redirect, not decommission

**Decision**: For at least 90 days after Vector Advisory launches, `dev.janus.sc0red.com` (and equivalents) returns HTTP 301 redirects to `vector.sc0red.com` for the matching path. After 90 days, the old host can be decommissioned; remove the Route 53 record.

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Decommission immediately at launch | Breaks every internal bookmark, every email link in the wild, every deck slide that screenshots the URL. Avoidable pain. |
| Keep redirect indefinitely | Long tail of stale URLs in search engines / docs. After 90 days the cost of the redirect (DNS + cert) outweighs its value. |
| Display a "we've moved" banner instead of redirect | Worse UX than a clean redirect; the user has to click again. |

**Trade-off**: 90-day window means the launch isn't fully clean for a quarter. Acceptable cost for not-breaking-things.

### 3. Per-environment hostname pattern

**Decision**: Three customer hosts, one per environment:
- Development: `dev.vector.sc0red.com`
- Testing: `testing.vector.sc0red.com`
- Production: `vector.sc0red.com`

The sub-subdomain pattern keeps environments visually distinct (a developer landing on `dev.vector.sc0red.com` knows they're not on prod) and matches the existing convention (`dev.janus.sc0red.com`).

**Alternatives considered:**
- `vector-dev.sc0red.com` / `vector-testing.sc0red.com` / `vector.sc0red.com` — flat at the same level. Less convention-following; production looks like the parent of the others, which is misleading.
- Promotion-based aliasing (`vector.sc0red.com` always points to the latest stable) — too clever, breaks intuition for non-prod testing.

**Trade-off**: ACM cert needs to cover three hostnames or a wildcard `*.vector.sc0red.com`. Minor cost.

### 4. Brand text strategy — search + replace, with curation

**Decision**: Treat the rename as primarily a string substitution (`Janus` → `Vector Advisory` in customer-visible contexts), but explicitly curate the high-stakes copy: page titles, login / signup brand block, marketing landing page tagline, email templates. Bulk replacement of incidental mentions; hand-curate the headline strings.

**Implication for the work**: tasks split into "automated find-and-replace pass" (covered by `tasks.md` step 2) and "hand-edit headline copy" (step 3). The hand-edit list is small (under 10 strings); the bulk pass covers the long tail.

**Trade-off**: Finding-and-replacing risks accidentally changing strings that should stay (e.g., "JanusStack" the CDK class). Mitigation: the substitution scope is restricted to specific file types and excludes infrastructure files. Tasks list documents the exact glob.

### 5. Section reorder anchored to advisory reading flow

**Decision**: The new analysis-page order is:

```
1. AnalysisHeader                  (unchanged)
2. AnalysisOverviewCards           (unchanged — score + radar)
3. TopActionsCallout                (unchanged)
4. ValueChainDiagram                ← MOVED UP from old position 7
5. EbitdaSection                    ← MOVED UP from old position 11
6. RiskBreakdown                    ← MOVED DOWN from old position 4
7. ValueLeverSummary + OpportunitiesList + Sc0redCTABanner
                                    ← MOVED DOWN from old positions 5–7
8. Re-analysis progress + DocumentUpload (interactive footer, unchanged)
```

The advisory narrative reads: "Here's the company → here's an at-a-glance score → here are the immediate plays → here's how the business actually works → here's where AI moves the financial outcome → here are the specific risks and opportunities to act on → upload more documents to refine."

**Alternatives considered:**
- Risk first ("here's why this matters") — the current order. An analyst's framing.
- Opportunities first ("here's what to do") — strong advisory move but skips the "why."
- The decided order — leads with company mechanics, ends with action. Closest to how a Vector consultant would walk a client through the company.

**Trade-off**: Existing user habits / muscle memory get disrupted. Acceptable: there are no external users to disrupt yet (no paying customers), and internal stakeholders adjust quickly.

### 6. PDF mirrors screen order

**Decision**: `PrintReport.tsx` reorders to match. New PDF section flow:
- Cover → Executive Summary → Top Actions → **Value Chain → EBITDA → Risk Profile → AI Opportunity Roadmap** → Methodology Appendix → Back Cover.

**Alternative considered:** Keep the PDF in the order from `improve-pdf-export-content` (Risk → Opportunities → EBITDA → Value Chain). Rejected: a PDF that tells a different story than the on-screen artifact creates cognitive whiplash for buyers who flip between the two.

The polished-pdf-export capability spec gets a delta to update the section-order requirement.

### 7. CSS / brand alignment is a curated audit, not a redesign

**Decision**: A focused review of the sc0red.com design language — primary palette, typography, spacing scale, accent treatment — and adjustment of design tokens in Janus's CSS where they diverge from the company site. Specifically NOT a component-by-component restyle. The audit produces a small list of token changes; if it grows beyond ~10 token adjustments, scope spills into a separate change.

**Why this scope**: a full visual rework is a multi-week project; a token-level alignment is days. Goal here is "looks like family," not "perfect visual harmony."

### 8. Logo asset replacement

**Decision**: `frontend/public/janus-logo.png` is replaced by a `vector-advisory-logo.png` (or `vector-logo.svg` if we get a vector asset from design). Five components reference the file via `<img src="/janus-logo.png" alt="Janus">` — all are updated to the new path + alt text. The old PNG can be deleted post-cutover.

**Trade-off**: Cache busting — if any user has the old logo cached, they'll see it for a session. Acceptable; the page reload picks up the new file.

## Risks / Trade-offs

- **Risk**: Find-and-replace catches strings that should NOT change (e.g., commit messages quoting old logs, fixture data, error messages from before the rename).
  - **Mitigation**: substitution scope explicitly restricted in `tasks.md`; excludes `infrastructure/`, `backend/scripts/`, `backend/tests/`, all `.test.ts*` files, lock files, and `cdk.out/`. The hand-curated step covers the high-stakes copy directly.
- **Risk**: Cognito redirect URI / NextAuth callback config not updated in time, breaks login on the new host.
  - **Mitigation**: tasks gate the host cutover behind a verified Cognito allowlist update + a smoke-test login on a preview build.
- **Risk**: PDF export rendering breaks because the section order change interacts badly with `print-section--break-before` rules.
  - **Mitigation**: we just rebuilt the PDF; component composition is straightforward, just reordering JSX. Section-break rules are the same.
- **Risk**: Old `dev.janus.sc0red.com` host still serves the new code (because Amplify is configured to serve it from the same branch) but with the new brand, creating a confusing duplicate.
  - **Mitigation**: cutover plan in `tasks.md` — Amplify Janus host is set to 301 redirect to Vector host *before* the new brand goes live, eliminating the duplicate-serving window.
- **Risk**: SEO impact from URL change. Search engines need time to re-index `vector.sc0red.com`; internal links from social / docs may still hit the old URL.
  - **Mitigation**: 301 redirects preserve PageRank. Update internal docs, GitHub README, the company-site link from sc0red.com → Vector. Submit an updated sitemap to Google Search Console.
- **Risk**: Internal cognitive friction — devs have to remember "we say Vector publicly but the code says janus." Onboarding cost.
  - **Mitigation**: a single-paragraph note in `CLAUDE.md` + `README.md` explaining the convention. Also flagged in the proposal's Non-Goals.
- **Risk**: The reorder regresses the existing PDF-export visual verification (we shipped that recently and it's already paid in customer attention).
  - **Mitigation**: re-run the visual verification gate from `improve-pdf-export-content` (capture before/after on three representative analyses) as part of this change's rollout. Reuses the existing `mint-print-url.mjs` script.
- **Risk**: Brand assets are missing — we don't yet have a finalised Vector Advisory logo file.
  - **Mitigation**: tasks include a "logo handoff" gate; if the asset isn't ready by implementation, ship with a typographic-only treatment (Vector Advisory wordmark) and add the icon when available. Acceptable for launch; not blocking.
- **Risk**: The repo name `SC0RED/janus` is visible in PR URLs / git remote / CI logs / issue links. Not changing it means external observers (auditors, prospects clicking a link) see "janus" anyway.
  - **Mitigation**: accept this. Repo rename is a separate, larger change with its own ripple effects (Amplify GitHub PAT, deploy keys, branch protections). Worth doing later as a clean follow-up if external visibility becomes a real concern.

## Migration Plan

This is a customer-visible rename, so launch order matters:

```
Step 1 — Pre-launch (development branch)
  - Land all code changes on `development`. Vector host serves from
    Amplify; Cognito allows the new redirect URI; old Janus host
    continues to serve the OLD brand until cutover.
  - Verify on `dev.vector.sc0red.com` that login + scan + analysis
    + PDF export all work.

Step 2 — Cutover gate
  - Switch the OLD `dev.janus.sc0red.com` Amplify domain to 301-
    redirect to `dev.vector.sc0red.com`. Verify with curl + browser.
  - The new brand is now the only experience customers see.

Step 3 — Document propagation
  - Update sc0red.com company website to link to the new URL.
  - Update README, CLAUDE.md, and any internal docs referencing
    the old host.

Step 4 — Promote to testing
  - Open dev → testing PR; same steps repeat for the testing host.

Step 5 — Promote to production
  - Open testing → production PR; same steps for production host.

Step 6 — Decommission window
  - 90 days after production cutover, remove the old Route 53
    records and the Amplify domain configs for the Janus hosts.
```

**Rollback strategy**: if anything breaks customer-visible after step 2, swap the redirect back so `dev.janus.sc0red.com` serves the codebase directly again. The brand text on the page is the only customer-visible thing that needs to revert; everything else (Amplify deployment, AWS resources, data) is unchanged. Rollback is fast.

## Open Questions

- **Logo asset**: who's producing the Vector Advisory mark, and by when? If not ready by implementation, ship with the typographic wordmark only.
- **Tagline / headline copy**: "Vector Advisory — AI Risk & Strategic Intelligence" is my placeholder. Final copy needs leadership sign-off before merging.
- **CSS palette source of truth**: is sc0red.com's design language captured anywhere reusable (a Figma file, a brand guide), or do we audit by visual comparison? If the latter, the audit is approximate.
- **Email-from address**: invitation emails currently say "Janus by SignalField" in the footer. Does the rebrand also update sender display name, or does the tech-side `from:` (e.g., `noreply@sc0red.com`) stay unchanged?
- **Sitemap / SEO**: do we have an existing `sitemap.xml` that needs regenerating, or should we add one as part of the rename for re-indexing speed?
- **Per-environment naming**: confirm `dev.vector.sc0red.com` / `testing.vector.sc0red.com` / `vector.sc0red.com` is the desired hostname pattern, vs. some flatter alternative.
