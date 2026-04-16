import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => '/analysis/test-id',
}))

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: { user: { name: 'Test' } } }),
    signOut: vi.fn(),
}))

import AnalysisHeader from '@/components/analysis/AnalysisHeader'

describe('AnalysisHeader', () => {
    it('renders company name', () => {
        render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" tier="high" />)
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    })

    it('renders dashboard breadcrumb link', () => {
        render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" tier="high" />)
        expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })

    it('renders industry badge when provided', () => {
        render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" industry="SaaS" tier="high" />)
        expect(screen.getByText('SaaS')).toBeInTheDocument()
    })

    it('does not render industry badge when not provided', () => {
        render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" tier="high" />)
        expect(screen.queryByText('SaaS')).not.toBeInTheDocument()
    })

    it('renders company URL when provided', () => {
        render(
            <AnalysisHeader
                analysisId="test-id"
                companyName="Acme Corp"
                companyUrl="https://acme.com"
                tier="high"
            />
        )
        expect(screen.getByText('https://acme.com')).toBeInTheDocument()
    })

    it('renders Export PDF button', () => {
        render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" tier="high" />)
        expect(screen.getByText('Export PDF')).toBeInTheDocument()
    })

    it('renders delete button', () => {
        render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" tier="high" />)
        expect(screen.getByText('Delete Analysis')).toBeInTheDocument()
    })

    it('renders Portfolio breadcrumb when scanId is present', () => {
        render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" tier="high" scanId="scan-123" />)
        const portfolioLink = screen.getByText('Portfolio')
        expect(portfolioLink).toBeInTheDocument()
        expect(portfolioLink.closest('a')).toHaveAttribute('href', '/portfolio/scan-123')
    })

    it('does not render Portfolio breadcrumb when scanId is absent', () => {
        render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" tier="high" />)
        expect(screen.queryByText('Portfolio')).not.toBeInTheDocument()
    })
})
