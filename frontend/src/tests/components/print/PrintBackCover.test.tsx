import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintBackCover from '@/components/print/PrintBackCover'

describe('PrintBackCover', () => {
    it('renders the CTA heading and contact link when there are opportunities', () => {
        render(<PrintBackCover hasOpportunities={true} />)
        expect(screen.getByText('Next Steps')).toBeInTheDocument()
        expect(screen.getByText('sc0red can help you capture these opportunities')).toBeInTheDocument()
        // Anchor href attr is set from getSc0redContactUrl().
        const link = screen.getByRole('link')
        expect(link.getAttribute('href')).toMatch(/^https?:\/\//)
    })

    it('returns null when there are no opportunities', () => {
        const { container } = render(<PrintBackCover hasOpportunities={false} />)
        expect(container.firstChild).toBeNull()
    })
})
