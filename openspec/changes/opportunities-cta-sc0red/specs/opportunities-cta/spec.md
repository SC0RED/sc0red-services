## ADDED Requirements

### Requirement: sc0red CTA banner renders at the bottom of the opportunities list
The `OpportunitiesList` component SHALL render a single sc0red call-to-action banner after the last opportunity card whenever one or more opportunities are visible in the current filter.

#### Scenario: Banner appears with opportunities present
- **WHEN** the opportunities list renders with at least one opportunity (under the active filter)
- **THEN** a sc0red CTA banner appears below the last opportunity card

#### Scenario: Banner hidden when filter returns zero opportunities
- **WHEN** a lever filter (Revenue / Cost / Both) is applied and the filtered list is empty
- **THEN** the sc0red CTA banner is NOT rendered

#### Scenario: Banner hidden when no opportunities exist at all
- **WHEN** an analysis has zero opportunities
- **THEN** the sc0red CTA banner is NOT rendered

### Requirement: Banner is collapsed by default and expandable
The sc0red CTA banner SHALL render in a collapsed state by default, showing a single heading row with a chevron affordance. It SHALL expand on user interaction to reveal pitch copy and a CTA button, following the same `aria-expanded` / `aria-controls` pattern used elsewhere in the opportunity cards.

#### Scenario: Initial collapsed state
- **WHEN** the opportunities list first renders
- **THEN** the banner shows only its heading row with `aria-expanded="false"` and a downward chevron

#### Scenario: User expands the banner
- **WHEN** the user clicks the banner heading
- **THEN** `aria-expanded` becomes `"true"`, the chevron rotates, and the pitch paragraph plus CTA button become visible

#### Scenario: User collapses the banner
- **WHEN** the banner is expanded and the user clicks the heading again
- **THEN** the banner returns to collapsed state with `aria-expanded="false"`

### Requirement: CTA links to an env-configurable contact URL
The banner's call-to-action button SHALL link to the URL defined by `NEXT_PUBLIC_SC0RED_CONTACT_URL`, falling back to `https://www.sc0red.com/contact` when the environment variable is unset or empty. The link SHALL open in a new tab with safe `rel` attributes.

#### Scenario: Default URL when env var is unset
- **WHEN** `NEXT_PUBLIC_SC0RED_CONTACT_URL` is not defined
- **THEN** the CTA link has `href="https://www.sc0red.com/contact"`

#### Scenario: Override via env var
- **WHEN** `NEXT_PUBLIC_SC0RED_CONTACT_URL` is set to a non-empty value
- **THEN** the CTA link has `href` equal to that value

#### Scenario: Empty env var treated as unset
- **WHEN** `NEXT_PUBLIC_SC0RED_CONTACT_URL` is set to an empty string
- **THEN** the CTA link falls back to the default URL (not `href=""`)

#### Scenario: External link safety
- **WHEN** the CTA link renders
- **THEN** it has `target="_blank"` and `rel` containing both `noopener` and `noreferrer`

### Requirement: Per-opportunity vendor section relabeled "Tech Stack"
Each opportunity card in the expanded view SHALL display its `related_services` list under the heading **"Tech Stack"**. The heading **"Implementation Partners"** SHALL NOT appear anywhere in the opportunities list UI.

#### Scenario: Heading uses "Tech Stack"
- **WHEN** an opportunity card with non-empty `related_services` is expanded
- **THEN** the section heading reads "Tech Stack" (not "Implementation Partners")

#### Scenario: Vendor chips render unchanged
- **WHEN** an opportunity has `related_services: ["Datadog - Observability"]` and is expanded
- **THEN** the chip text "Datadog - Observability" renders inside the "Tech Stack" section using the existing `.badge.badge-neutral` styling

#### Scenario: Section hidden when no vendors
- **WHEN** an opportunity's `related_services` is missing or empty
- **THEN** the "Tech Stack" heading and its container are not rendered (matches current behavior)

### Requirement: PDF export mirrors the CTA and label changes
The analysis PDF export route SHALL render the same relabeling and sc0red CTA content as the React UI. Because a PDF is static, the CTA SHALL render inline (always visible, no collapse affordance), with the contact URL printed as visible text.

#### Scenario: PDF uses "Tech Stack" label
- **WHEN** a PDF is generated for an analysis whose opportunities have `related_services`
- **THEN** each opportunity's vendor chip section is headed "Tech Stack" (not "Implementation Partners")

#### Scenario: PDF includes sc0red CTA block
- **WHEN** a PDF is generated for an analysis with one or more opportunities
- **THEN** a single sc0red CTA block appears after the opportunities section, containing the heading, the pitch copy, and the contact URL rendered as visible text

#### Scenario: PDF omits CTA block when no opportunities
- **WHEN** a PDF is generated for an analysis with zero opportunities
- **THEN** the sc0red CTA block is not rendered

#### Scenario: PDF contact URL respects env var
- **WHEN** the PDF route generates its sc0red block
- **THEN** the printed URL equals `NEXT_PUBLIC_SC0RED_CONTACT_URL` if set to a non-empty value, else `https://www.sc0red.com/contact`
