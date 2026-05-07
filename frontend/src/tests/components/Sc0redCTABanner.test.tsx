import { render, screen, fireEvent } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/analytics/emitEvent', () => ({
    emit: vi.fn(() => Promise.resolve()),
}))

import Sc0redCTABanner from '@/components/Sc0redCTABanner'
import { emit } from '@/lib/analytics/emitEvent'

const mockEmit = vi.mocked(emit)

describe('Sc0redCTABanner', () => {
    const contactUrl = 'https://example.com/contact'
    const baseProps = {
        contactUrl,
        analysisId: 'assess-1',
        opportunityCount: 3,
        activeLeverFilter: null,
    } as const

    beforeEach(() => {
        mockEmit.mockClear()
    })

    afterEach(() => {
        vi.clearAllMocks()
    })

    it('renders the collapsed heading by default', () => {
        render(<Sc0redCTABanner {...baseProps} />)

        // Per `strategy-map-on-demand` Phase B: copy reframed from
        // opportunity-centric to analysis-centric since the banner now
        // appears at Beat 1.5 (before opportunities are shown).
        expect(screen.getByText('Dig deeper with a sc0red advisor')).toBeInTheDocument()
    })

    it('is collapsed initially (aria-expanded=false, pitch hidden)', () => {
        render(<Sc0redCTABanner {...baseProps} />)

        const toggle = screen.getByRole('button', { expanded: false })
        expect(toggle).toHaveAttribute('aria-expanded', 'false')
        expect(screen.queryByRole('link', { name: /Start the conversation/i })).not.toBeInTheDocument()
    })

    it('expands on click and reveals pitch copy plus CTA link', () => {
        render(<Sc0redCTABanner {...baseProps} />)

        fireEvent.click(screen.getByRole('button'))

        expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
        expect(screen.getByText(/Our PE-experienced advisors take you/i)).toBeInTheDocument()
        expect(screen.getByRole('link', { name: /Start the conversation/i })).toBeInTheDocument()
    })

    it('collapses again when the trigger is clicked a second time', () => {
        render(<Sc0redCTABanner {...baseProps} />)

        const toggle = screen.getByRole('button')
        fireEvent.click(toggle)
        expect(toggle).toHaveAttribute('aria-expanded', 'true')

        fireEvent.click(toggle)
        expect(toggle).toHaveAttribute('aria-expanded', 'false')
        expect(screen.queryByRole('link', { name: /Start the conversation/i })).not.toBeInTheDocument()
    })

    it('CTA link uses the passed contactUrl and safe external-link attrs', () => {
        render(<Sc0redCTABanner {...baseProps} />)

        fireEvent.click(screen.getByRole('button'))

        const link = screen.getByRole('link', { name: /Start the conversation/i })
        expect(link).toHaveAttribute('href', contactUrl)
        expect(link).toHaveAttribute('target', '_blank')
        const rel = link.getAttribute('rel') ?? ''
        expect(rel).toContain('noopener')
        expect(rel).toContain('noreferrer')
    })

    it('emits sc0red_cta_banner_expanded when opened', () => {
        render(<Sc0redCTABanner {...baseProps} opportunityCount={5} activeLeverFilter="Revenue Side" />)

        fireEvent.click(screen.getByRole('button'))

        expect(mockEmit).toHaveBeenCalledTimes(1)
        expect(mockEmit).toHaveBeenCalledWith('sc0red_cta_banner_expanded', {
            analysisId: 'assess-1',
            opportunityCount: 5,
            activeLeverFilter: 'Revenue Side',
        })
    })

    it('emits sc0red_cta_banner_collapsed when closed', () => {
        render(<Sc0redCTABanner {...baseProps} opportunityCount={2} />)

        const toggle = screen.getByRole('button')
        fireEvent.click(toggle) // expand
        fireEvent.click(toggle) // collapse

        expect(mockEmit).toHaveBeenCalledTimes(2)
        expect(mockEmit).toHaveBeenNthCalledWith(2, 'sc0red_cta_banner_collapsed', {
            analysisId: 'assess-1',
            opportunityCount: 2,
            activeLeverFilter: null,
        })
    })

    it('emits sc0red_cta_clicked when the CTA link is clicked', () => {
        render(<Sc0redCTABanner {...baseProps} opportunityCount={4} activeLeverFilter="Cost Side" />)

        fireEvent.click(screen.getByRole('button'))
        mockEmit.mockClear() // ignore the expand emit

        const link = screen.getByRole('link', { name: /Start the conversation/i })
        fireEvent.click(link)

        expect(mockEmit).toHaveBeenCalledTimes(1)
        expect(mockEmit).toHaveBeenCalledWith('sc0red_cta_clicked', {
            analysisId: 'assess-1',
            opportunityCount: 4,
            activeLeverFilter: 'Cost Side',
        })
    })
})
