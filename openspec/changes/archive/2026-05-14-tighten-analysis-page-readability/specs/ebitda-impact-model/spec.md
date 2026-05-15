## MODIFIED Requirements

### Requirement: Subtotal leaves render as compact chips inside their parent's band

Each leaf node attached to a subtotal SHALL render as a **compact chip** visually contained inside the same band as its parent. Chips SHALL be rendered in a single flex container that allows wrapping to a second row when the chip count exceeds the available horizontal space (``flex-wrap: wrap``). Chips SHALL be reachable in keyboard tab order between the band header above them and the next connector below.

The chip MUST be visually smaller than the band header — specifically, the chip's typical rendered width SHALL be ≤ 200 px and its rendered height SHALL be ≤ 110 px, so that three chips fit beside the band header on viewports ≥ 768 px without overflow.

**Chip color treatment** (updated under `tighten-analysis-page-readability`): the chip's semantic-type signal (revenue / cost / margin / subtotal) SHALL be carried only by a ``3px solid`` colored left border on the chip's outer element. The chip body MUST use neutral theme tokens:

- ``background: var(--bg-surface-2)``
- ``border: 1px solid var(--border-subtle)`` for the main (non-accent) borders
- ``color: var(--text-primary)`` for the leaf label
- ``color: var(--text-secondary)`` for the percentage-of-parent caption

Semantic-color tints on the chip background, semantic-color full borders, and semantic-color label text are forbidden — the chip MUST follow the "colored edge accent on neutral body" pattern shared with the strategy-map chip and the Value Impact card.

Each chip SHALL surface, at minimum:

- The leaf ``label`` (in ``var(--text-primary)``, NOT inside a heading element).
- The leaf ``value_range``.
- The leaf ``percentage_of_parent`` (when present).
- The ``ConfidenceIndicator`` (small variant) when the leaf carries a ``confidence_level``.
- An opportunity-link indicator row (one small dot per linked opportunity) when ``linked_opportunity_indices`` is non-empty.

#### Scenario: Leaves of a parent render inside the same band container

- **WHEN** the section is rendered with a subtotal that has leaves
- **THEN** the leaves render inside a flex container that is a descendant of the same band element as the parent header, AND that flex container has ``flex-wrap`` enabled so chips wrap when the row is narrow

#### Scenario: A chip's rendered footprint stays under the visual budget

- **WHEN** a leaf chip is rendered with all surfaces present
- **THEN** the chip's CSS dimensions yield a rendered footprint no larger than 200 × 110 px, so three chips fit side-by-side on viewports ≥ 768 px

#### Scenario: Chip body uses neutral theme tokens, semantic color only on the left edge

- **WHEN** a leaf chip with ``type: 'revenue'`` (or ``'cost'`` / ``'margin'`` / ``'subtotal'``) is rendered
- **THEN** the chip's ``background`` style equals ``var(--bg-surface-2)``, AND the chip's main ``border`` is ``1px solid var(--border-subtle)``, AND the chip's ``borderLeft`` is a ``3px solid`` declaration carrying the semantic accent (revenue green / cost red / margin blue / subtotal amber), AND the label element's ``color`` is ``var(--text-primary)``

#### Scenario: Chip does NOT bathe in semantic color

- **WHEN** any leaf chip is rendered
- **THEN** the chip's ``background`` style is NOT a semantic-color tint (e.g. ``rgba(34, 197, 94, 0.10)`` or any palette-derived RGBA), AND the chip's main ``border`` is NOT a semantic-color value, AND the label text ``color`` is NOT a hardcoded palette color

#### Scenario: Mobile layout wraps chips inside the band

- **WHEN** the section is rendered on a viewport < 768 px
- **THEN** chips wrap to additional rows within the same band container (single-column when the band is narrowest), AND no element of the section requires horizontal scroll

#### Scenario: Confidence chip survives the chip-color-treatment change

- **WHEN** a leaf chip renders with ``confidence_level: "medium"``
- **THEN** the chip contains a ``ConfidenceIndicator`` element with ``aria-label="Confidence: Medium"``

#### Scenario: Opportunity-linked leaf surfaces its links inline

- **WHEN** a leaf chip renders with ``linked_opportunity_indices: [0, 2]``
- **THEN** the chip is keyboard-focusable, AND a row of indicator dots renders inline on the chip with one dot per linked opportunity, AND each dot's HTML ``title`` attribute carries the opportunity's title plus value lever
