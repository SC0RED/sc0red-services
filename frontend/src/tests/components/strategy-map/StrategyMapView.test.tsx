import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import StrategyMapView from '@/components/strategy-map/StrategyMapView'

import { fullStrategyMap } from './_fixtures'

/**
 * `StrategyMapView` tests under the Phase-12 composition. Phase 6
 * deleted the React-Flow canvas and replaced the layout with the CSS-
 * grid table; Phase 12 trimmed the header to Mission + Vision only.
 * The section now composes:
 *
 *   1. ``StrategyMapHeader``  — Mission banner + Vision eyebrow only.
 *                                VP + Strategic Priorities live in
 *                                ``StrategyMapDetailsSection``
 *                                (rendered separately by AnalysisDetail
 *                                below the table; see that file's tests).
 *   2. ``StrategyMapTable``   — 4 perspective rows × N theme columns.
 *   3. ``CoreValuesStrip``    — bottom strip listing core values.
 *
 * Detailed table-routing assertions live in
 * ``StrategyMapTable.test.tsx``; this file owns the composition + the
 * header shape only.
 */

describe('StrategyMapView — structural composition', () => {
    it('renders the section root and the table renderer', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.getByTestId('strategy-map-view')).toBeInTheDocument()
        expect(screen.getByTestId('strategy-map-table')).toBeInTheDocument()
    })

    it('does not render the now-deleted React-Flow canvas', () => {
        // Phase 6 (``redesign-analysis-visuals`` D3) replaced the canvas
        // with the CSS-grid table. The canvas testid must be gone.
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.queryByTestId('strategy-map-canvas')).not.toBeInTheDocument()
    })

    it('does not render a confidence legend (P2 dropped chip confidence dots)', () => {
        // The legend explaining the chip-level confidence dots is dead
        // copy now that the dots themselves are gone.
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.queryByTestId('strategy-map-confidence-legend')).not.toBeInTheDocument()
    })

    it("does not render a gaps panel (Phase 2 removed What's Missing)", () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.queryByTestId('strategy-map-whats-missing')).not.toBeInTheDocument()
    })

    it('renders the core-values strip with a ProvenanceMarker for synthesised values', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.getByTestId('strategy-map-core-values-strip')).toBeInTheDocument()
        expect(screen.getByText(/Live our values:/)).toBeInTheDocument()
        expect(screen.getByText(/Care for customers/)).toBeInTheDocument()
        expect(screen.getAllByLabelText('AI-inferred').length).toBeGreaterThanOrEqual(1)
    })
})

describe('StrategyMapView — header shape (Mission + Vision only, Phase 12)', () => {
    it('renders the section title eyebrow', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.getByText('Strategy Map')).toBeInTheDocument()
    })

    it('renders the mission banner with the statement visible by default', () => {
        // Phase 6 dropped the click-to-expand pattern. The mission
        // statement must be visible without any interaction.
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.getByTestId('strategy-map-mission-banner')).toBeInTheDocument()
        expect(
            screen.getByText('Provide convenient food, beverages, and fuel to commuters.')
        ).toBeInTheDocument()
    })

    it('renders the vision statement always-visible as an eyebrow row', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.getByTestId('strategy-map-vision')).toBeInTheDocument()
        expect(screen.getByText(/To be the most appetizing convenience retailer/)).toBeInTheDocument()
    })

    it('does NOT render the value-proposition block inside the header', () => {
        // Phase 12 of redesign-analysis-visuals relocated VP +
        // Strategic Priorities OUT of the header and into a separate
        // ``<StrategyMapDetailsSection>`` below the table (see the
        // dedicated test file). The header now only carries Mission +
        // Vision per Diagnostic Tool Feedback #4.
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.queryByTestId('strategy-map-value-proposition')).toBeNull()
    })

    it('does NOT render the strategic-priorities list inside the header', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(screen.queryByTestId('strategy-map-strategic-priorities')).toBeNull()
    })

    it('renders no <details> disclosure elements — accordion removed', () => {
        // The previous header used three <details> elements as a
        // single-open accordion. Phase 6 flattened the layout. If a
        // future change re-introduces accordion behaviour, this test
        // is the canary.
        const { container } = render(<StrategyMapView strategyMap={fullStrategyMap} opportunities={[]} />)
        expect(container.querySelectorAll('details').length).toBe(0)
    })
})
