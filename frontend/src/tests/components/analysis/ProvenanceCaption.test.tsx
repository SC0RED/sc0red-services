import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import ProvenanceCaption from '@/components/analysis/ProvenanceCaption'

describe('ProvenanceCaption', () => {
    it('renders an estimate that shows its work', () => {
        render(
            <ProvenanceCaption
                provenance="derived_estimate"
                confidenceLevel="low"
                basis="~265 staff x debt-settlement revenue per head"
            />
        )
        expect(screen.getByText(/Estimated/)).toBeInTheDocument()
        expect(screen.getByText(/low confidence/)).toBeInTheDocument()
        expect(screen.getByText(/265 staff/)).toBeInTheDocument()
    })

    it('renders a reported figure with a citation link', () => {
        render(
            <ProvenanceCaption
                provenance="disclosed"
                confidenceLevel="high"
                basis="2024 press release"
                citations={[{ url: 'https://example.com/pr', title: '2024 results' }]}
            />
        )
        expect(screen.getByText(/Reported/)).toBeInTheDocument()
        const link = screen.getByRole('link', { name: '2024 results' })
        expect(link).toHaveAttribute('href', 'https://example.com/pr')
    })

    it('renders the hostname when a citation has no title', () => {
        render(
            <ProvenanceCaption
                provenance="disclosed"
                basis="b"
                citations={[{ url: 'https://www.sec.gov/filing' }]}
            />
        )
        expect(screen.getByRole('link', { name: 'sec.gov' })).toBeInTheDocument()
    })

    it('renders nothing when there is no provenance or basis (legacy record)', () => {
        const { container } = render(<ProvenanceCaption />)
        expect(container).toBeEmptyDOMElement()
    })
})
