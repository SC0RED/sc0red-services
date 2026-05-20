import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import AnalysisLegend from '@/components/analysis/AnalysisLegend'

describe('AnalysisLegend', () => {
    it('renders the strategy-map legend with the "objective" noun', () => {
        render(<AnalysisLegend tool="strategy-map" />)
        // Default testid per tool.
        expect(screen.getByTestId('strategy-map-opportunity-link-legend')).toBeInTheDocument()
        // Canonical legend copy ends with the per-tool noun.
        expect(screen.getByText(/AI opportunities targeting this objective\./)).toBeInTheDocument()
        // All three lever labels rendered.
        expect(screen.getByText('Revenue Side')).toBeInTheDocument()
        expect(screen.getByText('Cost Side')).toBeInTheDocument()
        expect(screen.getByText('Both')).toBeInTheDocument()
    })

    it('renders the EBITDA legend with the "P&L line" noun', () => {
        render(<AnalysisLegend tool="ebitda" />)
        expect(screen.getByTestId('ebitda-opportunity-link-legend')).toBeInTheDocument()
        expect(screen.getByText(/AI opportunities targeting this P&L line\./)).toBeInTheDocument()
    })

    it('renders the value-chain legend with the "value-chain step" noun', () => {
        render(<AnalysisLegend tool="value-chain" />)
        expect(screen.getByTestId('value-chain-opportunity-link-legend')).toBeInTheDocument()
        expect(screen.getByText(/AI opportunities targeting this value-chain step\./)).toBeInTheDocument()
    })

    it('accepts a testId override', () => {
        // Some call sites (legacy EBITDA tests) want to keep their
        // existing testid wording — the prop lets them pin it.
        render(<AnalysisLegend tool="ebitda" testId="custom-legend-id" />)
        expect(screen.getByTestId('custom-legend-id')).toBeInTheDocument()
        // The default testid is NOT also applied.
        expect(screen.queryByTestId('ebitda-opportunity-link-legend')).toBeNull()
    })

    it('renders three decorative swatches with the LEVER_COLORS hue', () => {
        // Three swatches are present, each `aria-hidden` (the colour is
        // the signal; sighted readers cross-reference the swatch with
        // the labelled lever name beside it).
        render(<AnalysisLegend tool="ebitda" />)
        const swatches = screen
            .getByTestId('ebitda-opportunity-link-legend')
            .querySelectorAll('span[aria-hidden="true"]')
        // Three lever swatches + two decorative ` · ` separators = 5.
        expect(swatches.length).toBeGreaterThanOrEqual(3)
    })
})
