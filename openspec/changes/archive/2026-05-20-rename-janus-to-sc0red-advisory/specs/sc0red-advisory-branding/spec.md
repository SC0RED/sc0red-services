## ADDED Requirements

### Requirement: Customer-facing product name is "sc0red Advisory"

Every customer-facing surface — page titles, marketing landing page, login / signup / oauth-authorize / accept-invite pages, sidebar brand block, settings copy, email templates, alt text on logo images, and footer copy — SHALL use the brand name "sc0red Advisory" instead of "Janus". Internal-facing strings (Python / Node package names, AWS resource names, CDK stack identifiers, Docker container names, file paths, code comments describing the codebase, source-control repository name, internal docstrings) SHALL retain their existing names — the rename is a positioning bet, not an architectural change.

#### Scenario: Page title reflects the new brand

- **WHEN** a user loads any authenticated page in the application
- **THEN** the browser tab title contains "sc0red Advisory"
- **AND** does not contain "Janus"

#### Scenario: Sidebar shows the sc0red Advisory wordmark

- **WHEN** a logged-in user views the dashboard sidebar
- **THEN** the brand block displays "sc0red Advisory" as the product name
- **AND** the alt text on the logo image is "sc0red Advisory"

#### Scenario: Marketing landing page describes the product as sc0red Advisory

- **WHEN** an unauthenticated visitor opens the marketing landing page
- **THEN** the hero, body copy, and footer reference "sc0red Advisory"
- **AND** the footer copyright line reads "© <year> sc0red Advisory · …"

#### Scenario: Invitation email uses sc0red Advisory branding

- **WHEN** a team member is invited and an invitation email is sent
- **THEN** the email subject, header brand element, body copy, and footer reference "sc0red Advisory"
- **AND** the previous "Janus by SignalField — AI Risk Intelligence for Private Equity" footer is replaced with the sc0red Advisory equivalent

#### Scenario: Internal resource names are unchanged

- **WHEN** an engineer inspects AWS resources or the codebase
- **THEN** Lambda functions, DynamoDB table, SQS queues, IAM roles, log groups, Secrets Manager paths, and CloudWatch dashboards retain `janus-*` naming
- **AND** Python / Node package metadata (`janus-backend`, `janus-frontend`) is unchanged
- **AND** CDK stack names (`Janus-development`, `Janus-staging`) are unchanged
- **AND** the source repository remains `SC0RED/janus`

### Requirement: Customer-facing host is `advisory.sc0red.com` (with old-host redirect for 90 days)

The customer-facing application SHALL be served from a sc0red Advisory-branded host per environment:

- Development: `dev.advisory.sc0red.com`
- Testing: `testing.advisory.sc0red.com`
- Production: `advisory.sc0red.com`

The previous Janus hosts (`dev.janus.sc0red.com`, `testing.janus.sc0red.com`, `janus.sc0red.com`) SHALL serve HTTP 301 redirects to the corresponding sc0red Advisory path for at least 90 days after the production cutover. After that window the old hosts MAY be decommissioned.

#### Scenario: sc0red Advisory loads from the new host

- **WHEN** a user navigates to `https://dev.advisory.sc0red.com`
- **THEN** the application loads and serves the sc0red Advisory-branded experience
- **AND** Cognito authentication, scans, analyses, and PDF export all work end-to-end

#### Scenario: Old Janus URL redirects to the matching sc0red Advisory path

- **WHEN** a user navigates to `https://dev.janus.sc0red.com/analysis/abc-123`
- **THEN** the response is HTTP 301 with `Location: https://dev.advisory.sc0red.com/analysis/abc-123`
- **AND** the user lands on the matching path on the new host

#### Scenario: NextAuth callback URLs accept the new host

- **WHEN** a user signs in on the new sc0red Advisory host
- **THEN** the Cognito redirect URI for that environment includes `https://dev.advisory.sc0red.com/api/auth/callback/cognito` (and the testing / production equivalents)
- **AND** the NextAuth flow completes without redirect-mismatch errors

### Requirement: Analysis page renders sections in advisory-narrative order

The analysis detail screen SHALL render sections in an order that walks the reader from company-level context to specific actions, anchoring the advisory positioning. Below the existing header / overview cards / top actions block, the order SHALL be:

1. **Value Chain Analysis** — how the business operates (was previously after Opportunities)
2. **EBITDA Impact Model** — where AI moves the financial outcome (was previously last)
3. **Risk Profile** — risk breakdown by category (was previously second after the score)
4. **AI Opportunity Roadmap** — value-lever-grouped opportunities (was previously third)
5. The interactive footer (re-analysis state, document upload) SHALL remain at the bottom of the page

The analysis-page section ordering does not introduce or remove sections — every section that exists today SHALL continue to render under its existing data-availability conditions.

#### Scenario: Analysis with full data renders sections in advisory order

- **WHEN** an analysis with risk scores, opportunities, EBITDA tree, and value chain is rendered
- **THEN** the on-page section order below the overview cards is: Top Actions → Value Chain → EBITDA → Risk Profile → Opportunities → footer
- **AND** every section renders the same component as before the rename

#### Scenario: Sparse analysis still skips empty sections cleanly

- **WHEN** an analysis lacks an EBITDA tree or value chain
- **THEN** that section is omitted exactly as it was before the reorder
- **AND** the surrounding sections close up the gap without leaving a blank space

### Requirement: CSS / brand palette aligns with the sc0red.com design language

Frontend design tokens (typography, primary palette, accent colours, spacing scale) SHALL be reviewed against the sc0red.com company-site design language and adjusted where they materially diverge. The scope is a token-level audit — primary CSS variables in `globals.css` and any per-component overrides that contradict — not a component-by-component restyle.

#### Scenario: Primary brand colour matches the company site

- **WHEN** an engineer compares the application's primary accent colour to the sc0red.com primary accent
- **THEN** the values match (within minor browser-render tolerance)
- **AND** the design token name reflects the alignment

#### Scenario: Typography scale aligns with the company site

- **WHEN** an engineer compares the application's heading font, body font, and font-weight scale to the company site
- **THEN** the values match the sc0red.com design language
- **AND** existing Janus-era component styles that set inconsistent fonts are updated
