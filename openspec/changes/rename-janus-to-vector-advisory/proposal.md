## Why

The product currently shipped as **Janus** is being repositioned as **Vector Advisory** at `vector.sc0red.com` to align with sc0red's company narrative — "AI tools + advisory for mid-market PE." The rename is a positioning bet: "Janus" is mythological and gives no clue what the product does; "Vector Advisory" is directional, signals strategic intent, and frames the product as an advisory companion rather than a risk-score generator. The reorder of analysis sections (value chain → EBITDA tree → risk + opportunities) reinforces the new narrative — leading with how the business *works* rather than with a risk score, the way an advisor would walk a client through their company. CSS / brand alignment with `sc0red.com` makes Vector Advisory feel like a member of the sc0red product family rather than a one-off tool.

This change is **customer-visible only**. Internal infrastructure (Lambda names, DynamoDB table, SQS queues, IAM resource names) keeps the `janus-*` naming because renaming infra resources would require risky data migrations for zero customer value. The brand is the wrapper; the wiring stays.

## What Changes

- **URL**: customer-facing host changes from `dev.janus.sc0red.com` (and equivalents in testing / production) to `vector.sc0red.com`. Amplify branch domain is updated; the Janus host either redirects to Vector or stops being served. **BREAKING for bookmarks** — but the redirect mitigates.
- **Brand text and assets**:
  - Page titles: `"Janus — AI Risk & Opportunity Platform"` → `"Vector Advisory — AI Risk & Strategic Intelligence"` (or close equivalent — final wording lives in design.md).
  - Marketing landing page (`frontend/src/app/page.tsx`): every `Janus` mention replaced; tagline + footer updated.
  - Logo: `frontend/public/janus-logo.png` replaced with the Vector Advisory mark; consumers (`<img alt="Janus">` in 5 components) updated.
  - Sidebar brand block, login / signup / oauth-authorize / accept-invite pages: brand text + alt updated.
  - Settings page copy: "Choose how Janus looks…" → "Choose how Vector Advisory looks…"
  - `useTheme` hook docstring: "Theme system for the Janus webapp" → "Theme system for the Vector Advisory webapp".
- **Email templates**: `backend/src/handlers/templates/invitation_email.html` brand text + footer rewritten.
- **Analysis page section order** (`AnalysisDetail.tsx`):
  - Was: header → score+radar → top actions → risk → opportunities → value chain → re-analysis → documents → EBITDA.
  - **Now**: header → score+radar → top actions → **value chain → EBITDA → risk + opportunities** → re-analysis → documents.
  - The strategy-map section (a separate change, `ai-strategy-map`) will land at the top and is deliberately out of scope here.
- **PDF export section order** (`PrintReport.tsx`): mirrors the analysis page reorder — Cover → Executive Summary → Top Actions → **Value Chain → EBITDA → Risk Profile → Opportunity Roadmap** → Methodology → Back Cover.
- **CSS / brand palette alignment** with `sc0red.com`: typography, accent colours, spacing reviewed against the company-site design language; aligned where current Janus styling diverges.
- **READMEs and docs**: `README.md`, `DOCUMENTATION.md`, and `CLAUDE.md`'s "Janus — Claude Code Instructions" header retitled. Internal references to "the Janus codebase" stay where they describe the *codebase* (which still has `janus-*` resource names); only customer-facing language flips.
- **NOT changing**:
  - Repository name (`SC0RED/janus` stays).
  - Internal Python / Node package names (`janus-backend`, `janus-frontend` stay).
  - CDK stack names (`Janus-development`, `Janus-staging` stay).
  - AWS resource names (Lambda functions, DynamoDB table, SQS queues, IAM roles, log groups, Secrets Manager paths, CloudWatch dashboards) all keep `janus-*` prefixes.
  - Docker container names, dev DynamoDB table (`janus-dev`).
  - Test fixtures, internal docstrings that don't surface to customers.

## Capabilities

### New Capabilities
- `vector-advisory-branding`: Defines the customer-facing brand requirements for the rebranded product — product name, URL, page titles, brand asset usage, email-template branding, and the analysis-page section order that anchors the advisory narrative. Lives at `openspec/specs/vector-advisory-branding/spec.md` post-archive.

### Modified Capabilities
- `polished-pdf-export`: The existing section-order requirement (currently Cover → Executive Summary → Risk Profile → Opportunities → EBITDA → Value Chain → Methodology) is replaced with the advisory-narrative order (Cover → Executive Summary → Top Actions → Value Chain → EBITDA → Risk Profile → Opportunities → Methodology → Back Cover). The brand-text scenarios (cover eyebrow, footer template) shift from "sc0red · AI Risk Report" to the Vector Advisory brand strings.

## Impact

- **Frontend** (10–15 files): every page that renders the brand string, logo, alt text, or page title; `AnalysisDetail.tsx` reorders existing sections (no new components); `PrintReport.tsx` mirrors the reorder; CSS tokens updated where palette diverges from sc0red.com.
- **Backend** (1 file): `invitation_email.html` brand text + footer.
- **Infrastructure** (1 file): `infrastructure/stacks/amplify_construct.py` — Amplify branch domain config flips from `dev.janus.sc0red.com` to `vector.sc0red.com` (and testing/production equivalents).
- **DNS / CDN**: a new Route 53 record (or Amplify-managed equivalent) for `vector.sc0red.com`; the existing `dev.janus.sc0red.com` either keeps serving with a redirect to `vector.sc0red.com` for ~3 months, or is decommissioned at the same time as the launch (decision in design.md).
- **Auth / Cognito**: redirect URIs and allowed origins on the Cognito app client need to include the new host. NextAuth callback URL config follows.
- **Tests**: Playwright E2E setup files reference `dev.janus.sc0red.com` host — updated. Unit tests using "Janus" in fixtures / mock brand strings updated where the assertion is on customer-visible text. No internal-fixture renames.
- **CI / deploy workflows**: variables referencing `FRONTEND_DOMAIN` or hardcoded host strings checked; CDK env config updated per environment.
- **Documentation**: README, public-facing docs, marketing landing page copy. Internal architecture docs that describe codebase structure keep "janus" where they reference resource names that aren't being changed.
- **Observability**: any CloudWatch log queries, metric filters, or dashboards saved by hostname adjusted. Resource-name-based filters unchanged.
- **Out of scope**: AI strategy map generation (separate change `ai-strategy-map`), per-environment hostname strategy beyond development (testing / production hosts named `vector.sc0red.com` directly or `testing.vector.sc0red.com` — decision deferred to design.md).
