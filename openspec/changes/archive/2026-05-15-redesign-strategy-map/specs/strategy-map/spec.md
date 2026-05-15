## ADDED Requirements

### Requirement: Canvas chips never overflow their perspective bands

The 2D React Flow canvas SHALL guarantee that every chip is rendered entirely within the vertical bounds of its perspective band (FINANCIAL, CUSTOMER, INTERNAL PROCESSES, ORGANIZATIONAL CAPACITY). When a perspective contains more objectives than would fit in the default band height (e.g. an internal-processes theme with four objectives), the band height MUST grow to accommodate them rather than letting chips spill into adjacent bands.

The layout computation SHALL:

1. Determine the maximum number of chips per visual row across all themes in each band.
2. Compute the band height from that count plus the per-chip target height plus the per-row gap.
3. Position chips within their band using deterministic row/column indices.
4. Render via React Flow with the computed coordinates.

Band labels (FINANCIAL / CUSTOMER / etc.) and secondary labels (e.g. "What customers experience") MUST NOT visually overlap any chip in any band.

#### Scenario: Internal Processes theme with 4 objectives renders without overflow

- **WHEN** the internal-processes perspective has a theme with 4 objectives (e.g. I1.1, I1.2, I1.3, I1.4)
- **THEN** the Internal Processes band's rendered height grows to fit all 4 chips
- **AND** none of the chips spill into the Customer band above or the Organizational Capacity band below
- **AND** the band label "INTERNAL PROCESSES" is not overlapped by any chip

#### Scenario: Band labels remain visible

- **WHEN** any perspective band renders with any objective count
- **THEN** the band's label (e.g. "FINANCIAL", "CUSTOMER") and its secondary label (e.g. "Returns we generate", "What customers experience") render in dedicated space NOT shared with any chip
- **AND** the labels remain visible at the standard viewport zoom

### Requirement: Chip text truncation is responsive to available width

Chip text (the objective title) SHALL be truncated using the actual rendered chip width, not a fixed character cap. The truncation MUST use CSS `text-overflow: ellipsis` (or equivalent) so that:

- Wider chips show more text.
- Narrower chips truncate sooner.
- The truncation marker (`…`) appears at the end of the visible text.
- Hovering or focusing a truncated chip surfaces the full title via the existing tooltip mechanism.

#### Scenario: A wide chip shows more text than a narrow chip

- **WHEN** two chips in the same perspective render at different widths (e.g. the canvas is resized or zoom changes)
- **THEN** the wider chip displays more characters of its objective title before truncating
- **AND** the narrower chip's text truncates earlier
- **AND** both end with the `…` marker if truncated

#### Scenario: Tooltip reveals the full title on hover

- **WHEN** a user hovers or focuses a chip whose title is truncated
- **THEN** the chip's tooltip surfaces the full untruncated title
- **AND** the tooltip behaviour matches the existing hover/focus tooltip pattern

### Requirement: 2D canvas does not render a What's Missing section

The strategy-map 2D canvas SHALL NOT render a "What's Missing?" / gaps section. Strategy maps that contain no `whatsMissing` field (new analyses post-`redesign-strategy-map`) render as the perspective bands + chips + arrows only. Legacy strategy maps that may still have a `whatsMissing` field on the persisted record SHALL ignore the field at render time — no UI is shown for it.

#### Scenario: New strategy maps render with no gaps section

- **WHEN** a user views an analysis whose strategy map was generated post-`redesign-strategy-map`
- **THEN** the canvas renders perspective bands, chips, and arrows only
- **AND** no "What's Missing?" heading, gap chip, or gap list appears anywhere on the canvas or in the surrounding analysis-detail page

#### Scenario: Legacy strategy maps with whatsMissing data don't render the section

- **WHEN** a user views an analysis whose strategy map predates `redesign-strategy-map` and includes a `whatsMissing` field on the persisted record
- **THEN** the canvas renders without rendering the gap data
- **AND** the persisted `whatsMissing` field is ignored by the renderer (not deleted from the record, but not surfaced)
