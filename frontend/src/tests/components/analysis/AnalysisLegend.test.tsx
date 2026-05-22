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

    it('renders the quick-wins-matrix legend with matrix-specific copy (dot IS the opportunity)', () => {
        // On the matrix, the dot is the opportunity itself — not a node
        // an opportunity "targets". The legend copy flips accordingly.
        render(<AnalysisLegend tool="quick-wins-matrix" />)
        expect(screen.getByTestId('quick-wins-matrix-lever-legend')).toBeInTheDocument()
        expect(
            screen.getByText(/each dot is an AI opportunity, coloured by value lever\./i)
        ).toBeInTheDocument()
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

    it('renders SOLID swatches for strip-using tools (ebitda / strategy-map / value-chain)', () => {
        // Strip-using tools render solid 8 px dots via OpportunityDotStrip
        // on the canvas, so their legend swatches must match — solid.
        render(<AnalysisLegend tool="ebitda" />)
        const legend = screen.getByTestId('ebitda-opportunity-link-legend')
        // Pick the first lever swatch — its background is the lever
        // colour, NOT a neutral surface token.
        const firstSwatch = legend.querySelectorAll('span[aria-hidden="true"]')[0] as HTMLElement
        const style = firstSwatch.getAttribute('style') ?? ''
        expect(style).toContain('background: var(--lever-revenue)')
        // Solid swatches do not carry the donut box-shadow ring.
        expect(style).not.toContain('box-shadow')
    })

    it('renders DONUT swatches for the quick-wins-matrix tool (ring + neutral interior)', () => {
        // The matrix dots themselves are donuts (lever-coloured ring +
        // ``--bg-surface-3`` interior). The legend swatches must match
        // that vocabulary so a reader scans legend → chart → sidebar
        // and sees one consistent dot shape.
        render(<AnalysisLegend tool="quick-wins-matrix" />)
        const legend = screen.getByTestId('quick-wins-matrix-lever-legend')
        const firstSwatch = legend.querySelectorAll('span[aria-hidden="true"]')[0] as HTMLElement
        const style = firstSwatch.getAttribute('style') ?? ''
        // Neutral interior + lever-coloured inset ring.
        expect(style).toContain('background: var(--bg-surface-3)')
        expect(style).toContain('box-shadow')
        expect(style).toContain('var(--lever-revenue)')
    })
})
