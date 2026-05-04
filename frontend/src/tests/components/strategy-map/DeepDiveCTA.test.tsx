import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import DeepDiveCTA from '@/components/strategy-map/DeepDiveCTA'

describe('DeepDiveCTA', () => {
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
})
