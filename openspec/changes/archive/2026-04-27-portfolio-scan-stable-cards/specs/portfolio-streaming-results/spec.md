## ADDED Requirements

### Requirement: Portfolio page renders all company cards from t=0

The portfolio page SHALL render exactly one card per company in the scan from the moment the page loads, regardless of whether each company's analysis has started. The set of cards SHALL NOT grow during the scan run; only each card's state SHALL change.

#### Scenario: 50-company scan shows 50 cards immediately on load

- **WHEN** the user lands on `/portfolio/{scanId}` for a confirmed 50-company scan and the first company has just completed
- **THEN** the heatmap grid renders 50 cards (1 with a risk score, 49 in the `pending` state) with stable positions; subsequent polls do not add or remove cards

#### Scenario: All companies pending immediately after confirm

- **WHEN** the user is navigated to the portfolio page and zero companies have been picked up by a worker yet
- **THEN** the heatmap grid renders all `total_companies` cards in the `pending` state with `companyName` and `companyUrl` populated

#### Scenario: Cards never disappear once rendered

- **WHEN** a company card is in the `done` state and the user triggers a re-poll
- **THEN** the card remains in the `done` state with the same data; it is not removed and re-added

### Requirement: Portfolio cards are sorted by submission order

Portfolio cards SHALL render in the order the user submitted the companies at confirm time. Card positions SHALL NOT change as state transitions occur during the scan. The submission order SHALL be derived from an `orderIndex` field on each analysis entry returned by the API.

#### Scenario: Submission order is preserved through the run

- **WHEN** the user submitted 30 companies in a specific order and 10 of them have transitioned from `pending` → `scanning` → `done` while others are still `pending`
- **THEN** the cards render in the original submission order; the third company submitted appears in the third grid slot regardless of which companies have completed

#### Scenario: Fallback for legacy scans missing orderIndex

- **WHEN** the user views a scan whose link records pre-date the deployment (no `orderIndex` field)
- **THEN** the cards render sorted by `id` (today's behavior) without crashing

### Requirement: Pulsing dot + step label for scanning cards (accessible)

A card in the `scanning` state SHALL show a pulsing colored dot and the current `pipelineLabel` text (e.g. "Profiling risk..."). The card SHALL NOT render a numeric percentage or a linear progress bar. The pulse animation SHALL be disabled when the user has `prefers-reduced-motion: reduce` set; in that case the dot SHALL render with a static fixed opacity.

#### Scenario: Scanning card shows step label and animated dot

- **WHEN** a card's `state` is `scanning` and `pipelineLabel` is "Profiling risk..."
- **THEN** the card renders a pulsing dot indicator and the literal text "Profiling risk..."; no percentage or progress-bar element is in the DOM

#### Scenario: Reduced-motion preference disables the pulse

- **WHEN** the user has `prefers-reduced-motion: reduce` set in their OS/browser
- **THEN** the dot renders at fixed opacity and the CSS animation is disabled (verified by computed style on the dot element); the step label still renders

#### Scenario: Pulse uses a single shared keyframe

- **WHEN** the page renders 50+ scanning cards simultaneously
- **THEN** all cards share one `@keyframes` definition; per-card animation state is configured via `animation` properties only

## MODIFIED Requirements

### Requirement: Portfolio scan navigates to portfolio page after first company completes

After confirming a portfolio scan, the UI SHALL continue showing the progress bar (`ScanProgressPhase`) until at least one company analysis has a non-null `analyzedAt`. At that point, the UI SHALL navigate to `/portfolio/{scanId}`.

#### Scenario: First company completes within 60 seconds

- **WHEN** the user confirms 69 portfolio companies and the first analysis completes 40 seconds later
- **THEN** the progress bar page displays for ~40 seconds, then navigates to the portfolio page where 1 card is in the `done` state and 68 cards are in the `pending` or `scanning` state, all visible immediately

#### Scenario: No company completes (all fail or timeout)

- **WHEN** every company analysis fails or the scan reaches `status=failed`
- **THEN** the progress bar page transitions to an error state (existing `onFailed` behavior) — the user is NOT navigated to an empty portfolio page

#### Scenario: Single-company scan is unaffected

- **WHEN** the user submits a single-company scan (not portfolio)
- **THEN** the existing progress bar → redirect to `/analysis/{id}` flow is unchanged

### Requirement: Cards distinguish "Queued" from "Analyzing"

Portfolio grid cards SHALL render visual treatment driven by an explicit `state` field on each analysis entry, with four distinct states: `pending`, `scanning`, `done`, `failed`. The frontend SHALL NOT infer state from the presence or absence of `overallRiskScore`, `analyzedAt`, or `pipelineProgress`.

#### Scenario: Pending state — waiting for worker

- **WHEN** an analysis entry has `state: "pending"`
- **THEN** the card renders with reduced opacity, displays "Pending" as small text, and shows no risk score, no error badge, and no pulse animation

#### Scenario: Scanning state — pipeline in progress

- **WHEN** an analysis entry has `state: "scanning"` with `pipelineLabel: "Profiling risk..."`
- **THEN** the card renders the pulsing-dot affordance + the literal `pipelineLabel` text; no risk score is shown

#### Scenario: Done state — analysis complete

- **WHEN** an analysis entry has `state: "done"`
- **THEN** the card renders the risk score, the tier badge, and the tier-colored top border (today's "completed" treatment)

#### Scenario: Failed state — analysis errored

- **WHEN** an analysis entry has `state: "failed"`
- **THEN** the card renders the FAILED badge (today's failure treatment)

### Requirement: Portfolio page shows a progress strip while scan is running

While a portfolio scan has `status` other than `complete`, the portfolio page SHALL display a compact progress strip at the top showing the count of completed analyses out of total, with a thin progress bar.

#### Scenario: Progress strip shows live count

- **WHEN** the portfolio page renders with 12 of 69 analyses complete and scan status is `running`
- **THEN** a progress strip displays "12 of 69 done" with a progress bar filled to ~17%

#### Scenario: Progress strip updates on poll

- **WHEN** a new poll response arrives with 13 of 69 complete
- **THEN** the progress strip updates to "13 of 69 done" and the bar advances

### Requirement: Summary statistics are hidden until scan is complete

The portfolio page SHALL NOT display the summary statistics section (risk tier counts, average score) while the scan status is not `complete`. Summary stats SHALL appear only after the scan reaches `complete`.

#### Scenario: Running scan hides stats

- **WHEN** the scan status is `running` with 12 of 69 analyses done
- **THEN** the summary stats section is not rendered — the progress strip occupies that space

#### Scenario: Completed scan shows stats

- **WHEN** the scan status transitions to `complete`
- **THEN** the progress strip disappears and the summary statistics section renders with final tier counts and average risk score
