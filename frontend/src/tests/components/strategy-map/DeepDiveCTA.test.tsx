import { render, screen, fireEvent } from '@testing-library/react'
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'

// Mocks must be hoisted above the import of the component under test —
// the component imports the real `emit` at module load time, and the
// mock has to be in place before that runs.
vi.mock('@/lib/analytics/emitEvent', () => ({
    emit: vi.fn(() => Promise.resolve()),
}))

import DeepDiveCTA from '@/components/strategy-map/DeepDiveCTA'
import { emit } from '@/lib/analytics/emitEvent'

const mockEmit = vi.mocked(emit)

describe('DeepDiveCTA', () => {
    beforeEach(() => {
        mockEmit.mockClear()
    })

    afterEach(() => {
        vi.clearAllMocks()
    })

    it('renders the headline variant with a contact link', () => {
        render(<DeepDiveCTA analysisId="analysis-123" />)
        expect(screen.getByTestId('strategy-map-cta')).toBeInTheDocument()
        const link = screen.getByRole('link')
        expect(link).toHaveAttribute('target', '_blank')
        expect(link.getAttribute('href')).toContain('source=strategy-map')
        expect(link.getAttribute('href')).toContain('analysis-id=analysis-123')
    })

    it('appends gap query param for per-gap variants', () => {
        render(<DeepDiveCTA analysisId="a-1" gapId="G2" variant="inline" />)
        const link = screen.getByRole('link')
        expect(link.getAttribute('href')).toContain('gap=G2')
    })

    it('renders inline variant as a small text link without the headline card', () => {
        render(<DeepDiveCTA analysisId="a-1" variant="inline" />)
        expect(screen.queryByTestId('strategy-map-cta')).toBeNull()
        const link = screen.getByRole('link')
        expect(link.textContent?.toLowerCase()).toContain('discuss')
    })

    // ── Analytics ────────────────────────────────────────────────────────────
    //
    // The strategy map is positioned as the headline conversion artifact for
    // sc0red Advisory. The CTA must produce funnel signal — without these
    // events, the new product's conversion path is unmeasurable.

    it('emits sc0red_cta_rendered_strategy_map on mount (headline)', () => {
        render(<DeepDiveCTA analysisId="analysis-rm-1" />)

        expect(mockEmit).toHaveBeenCalledWith('sc0red_cta_rendered_strategy_map', {
            analysisId: 'analysis-rm-1',
            opportunityCount: 0,
            activeLeverFilter: null,
        })
    })

    it('emits sc0red_cta_rendered_strategy_map on mount (inline variant too)', () => {
        // Inline variant is the per-gap CTA; same surface, same signal.
        render(<DeepDiveCTA analysisId="analysis-rm-2" gapId="G1" variant="inline" />)

        expect(mockEmit).toHaveBeenCalledWith(
            'sc0red_cta_rendered_strategy_map',
            expect.objectContaining({ analysisId: 'analysis-rm-2' })
        )
    })

    it('emits sc0red_cta_clicked_strategy_map on link click (headline)', () => {
        render(<DeepDiveCTA analysisId="analysis-cl-1" />)
        mockEmit.mockClear() // ignore the on-mount rendered event

        fireEvent.click(screen.getByRole('link'))

        expect(mockEmit).toHaveBeenCalledWith('sc0red_cta_clicked_strategy_map', {
            analysisId: 'analysis-cl-1',
            opportunityCount: 0,
            activeLeverFilter: null,
        })
    })

    it('emits sc0red_cta_clicked_strategy_map on link click (inline)', () => {
        render(<DeepDiveCTA analysisId="analysis-cl-2" gapId="G3" variant="inline" />)
        mockEmit.mockClear()

        fireEvent.click(screen.getByRole('link'))

        expect(mockEmit).toHaveBeenCalledWith(
            'sc0red_cta_clicked_strategy_map',
            expect.objectContaining({ analysisId: 'analysis-cl-2' })
        )
    })

    it('does not fire the rendered event a second time on rerender with same analysisId', () => {
        const { rerender } = render(<DeepDiveCTA analysisId="analysis-stable" />)
        expect(mockEmit).toHaveBeenCalledTimes(1)

        rerender(<DeepDiveCTA analysisId="analysis-stable" gapId="G7" />)

        // Same analysis — should not double-emit. (gap change is not a new
        // CTA impression; it's the same CTA in a different position.)
        expect(mockEmit).toHaveBeenCalledTimes(1)
    })
})
