## ADDED Requirements

### Requirement: Domain terms have inline help tooltips

The webapp SHALL render a small `ⓘ` (info) icon next to PE-domain terms that benefit from explanation. Clicking or hovering the icon SHALL reveal a tooltip with a one-to-two-sentence explanation. Content SHALL come from a single shared registry, NOT inlined per-component.

#### Scenario: User hovers Risk Tier label

- **WHEN** the user hovers the ⓘ next to "Risk Tier" on `/analyses`
- **THEN** a tooltip appears explaining what Risk Tier means (e.g., "An aggregate severity classification: Low, Moderate, High, or Critical, derived from the risk score and pipeline outputs.")

#### Scenario: Same term explained consistently across surfaces

- **WHEN** the user hovers ⓘ next to "Risk Tier" on `/analyses` and again on `/analysis/{id}`
- **THEN** both tooltips display identical text (sourced from the same registry entry)

#### Scenario: Tap reveals tooltip on touch devices

- **WHEN** a user on a touch device taps the ⓘ icon
- **THEN** the tooltip appears; tapping outside dismisses it

### Requirement: Tooltips are accessible

Help tooltips SHALL be keyboard-focusable (Tab focuses the ⓘ trigger; Enter/Space reveals the tooltip). The tooltip content SHALL have an appropriate ARIA role (`role="tooltip"`) and be associated with the trigger via `aria-describedby`.

#### Scenario: Keyboard user reveals tooltip

- **WHEN** the user Tabs to a ⓘ icon and presses Enter
- **THEN** the tooltip becomes visible; the trigger has `aria-expanded="true"` (or equivalent)

#### Scenario: Screen reader associates tooltip with trigger

- **WHEN** a screen reader focuses the ⓘ trigger
- **THEN** the tooltip content is announced via the `aria-describedby` association

### Requirement: Initial term coverage spans the core PE concepts

The first ship of domain tooltips SHALL include explainers for at minimum: Risk Tier, Risk Score, EBITDA Tree, Value Lever (Revenue Side / Cost Side / Both), Active Lever Filter, Industry classification, Opportunity Impact Rating. Subsequent ships MAY add more terms.

#### Scenario: All listed terms render a help tooltip

- **WHEN** the user inspects the analyses table, the analysis detail page, the EBITDA tree, and the opportunities list
- **THEN** every listed term (Risk Tier, Risk Score, EBITDA Tree, Value Lever, Active Lever Filter, Industry, Impact Rating) has a `ⓘ` icon nearby with a registered tooltip
