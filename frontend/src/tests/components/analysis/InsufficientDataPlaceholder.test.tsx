import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

import InsufficientDataPlaceholder from '@/components/analysis/InsufficientDataPlaceholder'

describe('InsufficientDataPlaceholder', () => {
    it('renders the heading and body', () => {
        render(<InsufficientDataPlaceholder heading="Financial model not shown" body="No data." />)
        expect(screen.getByText('Financial model not shown')).toBeInTheDocument()
        expect(screen.getByText('No data.')).toBeInTheDocument()
    })

    it('renders no CTA when label/handler are omitted', () => {
        render(<InsufficientDataPlaceholder heading="H" body="B" />)
        expect(screen.queryByTestId('insufficient-data-cta')).not.toBeInTheDocument()
    })

    it('renders a clickable CTA when label and handler are provided', () => {
        const onCtaClick = vi.fn()
        render(
            <InsufficientDataPlaceholder
                heading="H"
                body="B"
                ctaLabel="Attach a document"
                onCtaClick={onCtaClick}
            />
        )
        const cta = screen.getByTestId('insufficient-data-cta')
        expect(cta).toHaveTextContent('Attach a document')
        fireEvent.click(cta)
        expect(onCtaClick).toHaveBeenCalledTimes(1)
    })

    it('uses a custom testId when provided', () => {
        render(<InsufficientDataPlaceholder heading="H" body="B" testId="ebitda-insufficient-data" />)
        expect(screen.getByTestId('ebitda-insufficient-data')).toBeInTheDocument()
    })
})
