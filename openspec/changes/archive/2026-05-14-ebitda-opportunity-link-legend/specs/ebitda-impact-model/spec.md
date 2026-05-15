## ADDED Requirements

### Requirement: EBITDA section documents the opportunity-link dot scale via an inline legend

The EBITDA Impact Model section SHALL render an inline legend that documents the meaning of the colored dots rendered at the bottom of each leaf chip. The legend SHALL identify each color, its corresponding value-lever category (``Revenue Side`` / ``Cost Side`` / ``Both``), and the overall semantic ("AI Opportunities targeting this P&L line").

The legend SHALL be gated on data presence: it MUST render only when at least one leaf node in the rendered tree carries a non-empty ``linked_opportunity_indices`` array. When no leaf carries any linked opportunity, the legend SHALL be absent (no chips render dots in that case, so the legend would have nothing to explain).

The legend SHALL use the same ``LEVER_COLORS`` palette via the existing ``--lever-revenue`` / ``--lever-cost`` / ``--lever-both`` theme tokens — the legend dots and the chip dots MUST drift together by construction.

The legend MUST be reachable via the test id ``ebitda-opportunity-link-legend`` so its presence and content can be asserted in tests.

#### Scenario: Legend renders when at least one leaf carries linked opportunities

- **WHEN** the EBITDA section is rendered with an ``EbitdaTreeResult`` whose tree contains at least one leaf with ``linked_opportunity_indices`` of length ≥ 1
- **THEN** an element with test id ``ebitda-opportunity-link-legend`` is present in the rendered DOM, AND that element's text content contains the strings "Revenue Side", "Cost Side", and "Both"

#### Scenario: Legend absent when no leaf carries linked opportunities

- **WHEN** the EBITDA section is rendered with a tree where every node's ``linked_opportunity_indices`` is empty or undefined
- **THEN** no element with test id ``ebitda-opportunity-link-legend`` is present in the rendered DOM

#### Scenario: Legend finds linked opportunities on a deeply-nested child leaf

- **WHEN** the EBITDA section is rendered with a tree whose top-level node has empty ``linked_opportunity_indices`` but a nested child leaf has ``linked_opportunity_indices: [0]``
- **THEN** the legend renders (the predicate walks children recursively)

#### Scenario: Legend dots draw from the same theme tokens as the chip dots

- **WHEN** the legend is rendered
- **THEN** the legend's three colored dots use ``background`` styles that reference ``var(--lever-revenue)``, ``var(--lever-cost)``, and ``var(--lever-both)`` respectively — the same tokens the chip dots use via ``LEVER_COLORS``
