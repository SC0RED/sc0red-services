## 1. Dark-theme token contrast lift (Part B — highest leverage)

- [x] 1.1 In ``frontend/src/app/globals.css`` under the ``:root`` selector, change ``--text-secondary`` from ``#8b9ac4`` to ``#a8b4d6`` and ``--text-tertiary`` from ``#4d5b7f`` to ``#7c8aaf``. Leave the ``[data-theme="light"]`` branch untouched.
- [x] 1.2 Verify the bump with a contrast-ratio sanity check (eyeballing or a contrast-checker browser extension): tertiary should now read clearly on the dark base background; secondary should feel comfortable, not glaring.

## 2. EBITDA chip: colored-left-border accent (Part A)

- [x] 2.1 In ``frontend/src/components/EbitdaNodeComponent.tsx``, restructure the ``LeafChip`` variant's ``chipStyle`` function: swap the semantic-color body for ``background: var(--bg-surface-2)``, the main border for ``border: 1px solid var(--border-subtle)``, AND add ``borderLeft: '3px solid ${colors.text}'`` carrying the accent. Drop the ``colors.bg`` + ``colors.border`` reads — only ``colors.text`` is used (for the left edge).
- [x] 2.2 In the same file, update the leaf label style (``chipLabelStyle`` or inline equivalent) to use ``color: 'var(--text-primary)'`` instead of the type-color accent. The label loses its green/red/etc. tint and becomes legible-neutral.
- [x] 2.3 The band-header (``BandHeader``) variant keeps its 4px colored left strip from PR #301 — unchanged. Confirm during the edit that nothing in the BandHeader branch is touched.
- [x] 2.4 Drop the now-unused ``bg`` and ``border`` fields from ``NODE_COLORS``. Only ``text`` survives — it's the source of the accent color for both the band-header strip and the chip left border.

## 3. Type-scale audit (Part C)

- [x] 3.1 Sweep ``frontend/src/components/EbitdaTree.tsx`` and ``frontend/src/components/EbitdaNodeComponent.tsx`` for inline ``fontSize`` values. Map each to one of the five canonical steps (``0.75 / 0.875 / 1 / 1.125 / 1.5 rem``). Replace.
- [x] 3.2 Sweep ``frontend/src/components/RiskBreakdown.tsx`` for inline ``fontSize`` values. Map each to a canonical step. Replace.
- [x] 3.3 Sweep ``frontend/src/components/OpportunitiesList.tsx`` for inline ``fontSize`` values. Map each to a canonical step. Replace.
- [x] 3.4 Sweep ``frontend/src/components/ValueChainDiagram.tsx`` for inline ``fontSize`` values. Map each to a canonical step. Replace.
- [x] 3.5 Sweep ``frontend/src/components/DocumentUpload.tsx`` for inline ``fontSize`` values. Map each to a canonical step. Replace.
- [x] 3.6 Sweep ``frontend/src/components/ValueLeverSummary.tsx`` for inline ``fontSize`` values. Map each to a canonical step. Replace.
- [x] 3.7 Sweep ``frontend/src/components/analysis/*.tsx`` (AnalysisHeader, AnalysisExecutiveStrap, AnalysisOverviewCards, AnalysisSection, EbitdaSection, TopActionsCallout, StrategyMapSlot, FailedAnalysisView, ReanalyzeProgressCard) for inline ``fontSize`` values. Map each to a canonical step. Replace. Three documented display-stat exceptions stay at their current sizes: ``AnalysisHeader`` ``<h1>`` at ``1.625rem``, ``AnalysisOverviewCards`` big risk-score number at ``2.5rem``, ``ValueLeverSummary`` lever-count at ``1.75rem``.
- [x] 3.8 Sweep ``frontend/src/components/strategy-map/*.tsx`` (StrategyMapView, StrategyMapHeader, StrategyMapCanvas, StrategyMapNode, DeepDiveCTA) for inline ``fontSize`` values. Map each to a canonical step. Replace.

## 4. Tests

- [x] 4.1 Update ``frontend/src/tests/components/EbitdaNodeComponent.test.tsx``'s band-header variant test set: the "border-left 4px solid" assertion stays. Add a new test on the chip variant: assert the chip's outer ``<article>`` has ``borderLeft`` of ``3px solid`` AND the chip's ``background`` style equals ``var(--bg-surface-2)`` AND the label's ``color`` equals ``var(--text-primary)``.
- [x] 4.2 Add an anti-regression test on the chip variant: assert NO descendant style contains a ``rgba(`` substring that matches the semantic-color palette (the chip body MUST NOT bathe in semantic color). This pins the "no chromatic bath" rule.
- [x] 4.3 Where existing tests in ``frontend/src/tests/`` assert specific inline ``fontSize`` values (e.g. ``expect(el.style.fontSize).toBe('0.8125rem')``), update to the new canonical step.
- [x] 4.4 Add a unit test asserting NO inline ``fontSize`` style in any rendered analysis-page component carries an off-scale value (``0.7rem`` / ``0.8125rem`` / ``0.9rem`` / ``0.9375rem`` / ``0.9875rem``). The test renders ``AnalysisDetail`` with a full fixture and walks the DOM for offending styles.

## 5. Verify + ship

- [x] 5.1 Run ``npm test -- --run`` in ``frontend/`` — all tests green.
- [x] 5.2 Run ``npx tsc --noEmit`` and ``npm run lint`` — clean.
- [x] 5.3 Run the ``architecture-reviewer`` agent (touches a global CSS file + 10+ frontend components + tests); resolve CRITICAL + MEDIUM findings before commit.
- [ ] 5.4 Visual verification on testing env (dark theme): the EBITDA section now matches the strategy-map aesthetic — neutral chip bodies with colored left edges, band headers still carrying the colored strip. Body text reads more clearly across every section. No section feels "too loud" or "too quiet".
- [ ] 5.5 Visual verification on testing env (light theme): the page renders identically to today (light tokens unchanged); EBITDA chips picked up the neutral-body + colored-left-edge treatment.
- [ ] 5.6 Cross-page spot check (dark theme): dashboard, admin, login surfaces reading the bumped tokens — verify the contrast lift looks intentional, not glaring, on those pages.
- [ ] 5.7 Commit, push, open PR against ``development``.
