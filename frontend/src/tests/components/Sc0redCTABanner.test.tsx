import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import Sc0redCTABanner from '@/components/Sc0redCTABanner'

describe('Sc0redCTABanner', () => {
    const contactUrl = 'https://example.com/contact'

    it('renders the collapsed heading by default', () => {
        render(<Sc0redCTABanner contactUrl={contactUrl} />)

        expect(screen.getByText('sc0red can help you capture these opportunities')).toBeInTheDocument()
    })

    it('is collapsed initially (aria-expanded=false, pitch hidden)', () => {
        render(<Sc0redCTABanner contactUrl={contactUrl} />)

        const toggle = screen.getByRole('button', { expanded: false })
        expect(toggle).toHaveAttribute('aria-expanded', 'false')
        expect(screen.queryByRole('link', { name: /Start the conversation/i })).not.toBeInTheDocument()
    })

    it('expands on click and reveals pitch copy plus CTA link', () => {
        render(<Sc0redCTABanner contactUrl={contactUrl} />)

        fireEvent.click(screen.getByRole('button'))

        expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
        expect(screen.getByText(/Our AI specialists implement opportunities/i)).toBeInTheDocument()
        expect(screen.getByRole('link', { name: /Start the conversation/i })).toBeInTheDocument()
    })

    it('collapses again when the trigger is clicked a second time', () => {
        render(<Sc0redCTABanner contactUrl={contactUrl} />)

        const toggle = screen.getByRole('button')
        fireEvent.click(toggle)
        expect(toggle).toHaveAttribute('aria-expanded', 'true')

        fireEvent.click(toggle)
        expect(toggle).toHaveAttribute('aria-expanded', 'false')
        expect(screen.queryByRole('link', { name: /Start the conversation/i })).not.toBeInTheDocument()
    })

    it('CTA link uses the passed contactUrl and safe external-link attrs', () => {
        render(<Sc0redCTABanner contactUrl={contactUrl} />)

        fireEvent.click(screen.getByRole('button'))

        const link = screen.getByRole('link', { name: /Start the conversation/i })
        expect(link).toHaveAttribute('href', contactUrl)
        expect(link).toHaveAttribute('target', '_blank')
        const rel = link.getAttribute('rel') ?? ''
        expect(rel).toContain('noopener')
        expect(rel).toContain('noreferrer')
    })
})
