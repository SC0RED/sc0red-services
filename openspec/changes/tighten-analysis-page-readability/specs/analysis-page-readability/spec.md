## ADDED Requirements

### Requirement: Body-text color tokens meet WCAG AA contrast on every supported theme

The frontend's body-text color tokens — ``--text-primary``, ``--text-secondary``, ``--text-tertiary`` — SHALL render at WCAG AA-normal contrast (≥ 4.5:1) or better against the corresponding ``--bg-base`` on every supported theme. The token *intent* SHALL be expressed consistently across themes: ``--text-primary`` for body content, ``--text-secondary`` for supporting copy, ``--text-tertiary`` for captions and labels.

The dark theme tokens MAY be visually different from the light theme tokens (different hex values, different perceived saturation) but the *role* and the contrast floor MUST match. A token that would render below 4.5:1 contrast on its theme's base background SHALL be retired or remapped, not used.

#### Scenario: Dark-theme tertiary text passes WCAG AA-normal

- **WHEN** a string rendered in ``var(--text-tertiary)`` is layered on ``var(--bg-base)`` on the dark theme
- **THEN** the computed contrast ratio is ≥ 4.5:1

#### Scenario: Dark-theme secondary text passes WCAG AA-normal with comfortable margin

- **WHEN** a string rendered in ``var(--text-secondary)`` is layered on ``var(--bg-base)`` on the dark theme
- **THEN** the computed contrast ratio is ≥ 7.0:1 (AA-normal with ≥ 50% headroom for dense content surfaces)

#### Scenario: Light-theme tokens preserve their existing intent

- **WHEN** the analysis-detail page is rendered in light mode
- **THEN** the same three tokens render at ≥ 4.5:1 contrast against the light ``--bg-base`` (the light theme already passes; this scenario pins the parity)

### Requirement: Semantic color appears only on edge accents, never on body content surfaces inside the analysis page

Components on the analysis-detail page that need to signal a semantic category (revenue / cost / margin / subtotal / risk-tier / value-lever) SHALL carry that signal **only on a single edge accent** — a colored top, left, right, or bottom border 2-4 px thick. Component body surfaces (background, full border, label text) SHALL use neutral theme tokens (``var(--bg-surface-*)``, ``var(--border-subtle)``, ``var(--text-primary)``, ``var(--text-secondary)``).

Semantic-color backgrounds, semantic-color full borders, and semantic-color label text — the "chromatic bath" pattern — are forbidden on the analysis page. They produce excess visual saturation and break the page's calm-with-accents aesthetic established by the strategy-map and Value Impact card patterns.

#### Scenario: EBITDA chip uses colored-left-border accent, neutral body

- **WHEN** an EBITDA leaf chip with ``type: 'revenue'`` is rendered
- **THEN** the chip's body background is ``var(--bg-surface-2)``, the chip's main border is ``1px solid var(--border-subtle)``, the chip's label text is ``var(--text-primary)``, AND the chip's left edge carries a ``3px solid`` semantic accent in the revenue palette color

#### Scenario: No analysis-page component sets a semantic-color background on its full surface

- **WHEN** any component on the analysis-detail page is rendered
- **THEN** no element's ``background`` style is a hardcoded ``rgba({type-color}, 0.10)`` or similar semantic-palette tint (the strategy-map perspective bands and the Value Impact card top-strip pattern remain the canonical exceptions — they carry color on a contained surface but not on per-item body content)

### Requirement: Inline font-size values converge on a five-step canonical scale

Frontend components rendered on the analysis-detail page SHALL use inline ``fontSize`` values drawn from the following canonical five-step scale, in ``rem`` units:

| Step | Value | Use |
|------|-------|-----|
| caption | ``0.75rem`` | helper text, dot labels, percentages |
| body-small | ``0.875rem`` | dense secondary copy, chip subtitles |
| body | ``1rem`` | section body, list items |
| heading-small | ``1.125rem`` | subheadings within a section |
| heading | ``1.5rem`` | section titles |

**Documented display-stat exceptions**: three surfaces render headline numbers that establish page identity at a glance and follow a display scale rather than the body type scale. These keep their existing custom sizes:

| Surface | Size | Rationale |
|---------|------|-----------|
| ``AnalysisHeader`` ``<h1>`` (company name) | ``1.625rem`` | Page identity — the title of the page. |
| ``AnalysisOverviewCards`` big risk-score | ``2.5rem`` | Focal headline statistic; first element the eye lands on. |
| ``ValueLeverSummary`` lever-count | ``1.75rem`` | Display-stat treatment on the Value Impact lever cards. |

All other inline ``fontSize`` values inside analysis components SHALL match one of the five steps above. Off-scale values (``0.6rem``, ``0.625rem``, ``0.65rem``, ``0.6875rem``, ``0.7rem``, ``0.78rem``, ``0.8rem``, ``0.8125rem``, ``0.85rem``, ``0.9rem``, ``0.9375rem``, ``0.9875rem``, ``1.05rem``, ``1.25rem``, etc.) SHALL be migrated to the nearest step.

#### Scenario: Analysis components use only canonical font-size steps

- **WHEN** any analysis-page component is rendered
- **THEN** every inline ``fontSize`` style value resolves to one of ``0.75rem``, ``0.875rem``, ``1rem``, ``1.125rem``, ``1.5rem``, OR to one of the documented display-stat exceptions (``1.625rem`` on the ``AnalysisHeader`` ``<h1>``, ``2.5rem`` on the ``AnalysisOverviewCards`` risk-score, ``1.75rem`` on the ``ValueLeverSummary`` lever-count)

#### Scenario: No off-scale font sizes survive the migration

- **WHEN** the analysis-page component tree is grepped for inline ``fontSize`` style values
- **THEN** values such as ``0.7rem``, ``0.8125rem``, ``0.9rem``, ``0.9375rem``, ``0.9875rem`` are absent from the rendered components
