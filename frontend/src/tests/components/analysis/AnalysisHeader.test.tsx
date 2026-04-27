import { screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

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

    describe('scan provenance (only for portfolio scans)', () => {
        it('renders breadcrumb + provenance link to /portfolio/{scanId} when scanType=portfolio', () => {
            render(
                <AnalysisHeader
                    analysisId="test-id"
                    companyName="Acme Corp"
                    tier="high"
                    scanId="scan-123"
                    scanType="portfolio"
                    scanSourceUrl="https://perotjain.com/"
                />
            )
            // Breadcrumb shows the prettified URL (not the literal "Portfolio" string)
            const breadcrumbLink = screen.getAllByText('perotjain.com')[0]
            expect(breadcrumbLink.closest('a')).toHaveAttribute('href', '/portfolio/scan-123')
            // "Part of:" provenance line renders too
            expect(screen.getByText(/Part of:/)).toBeInTheDocument()
            // Both labels resolve to the same scan
            const allLinks = screen.getAllByRole('link', { name: /perotjain\.com/ })
            allLinks.forEach((link) => {
                expect(link).toHaveAttribute('href', '/portfolio/scan-123')
            })
        })

        it('does not render Portfolio breadcrumb or provenance for standalone scans', () => {
            // Regression guard: pre-fix, the breadcrumb appeared whenever scanId
            // was set — including standalone scans, where /portfolio/{scanId}
            // makes no sense. Now the check is gated on scanType === 'portfolio'.
            render(
                <AnalysisHeader
                    analysisId="test-id"
                    companyName="Acme Corp"
                    tier="high"
                    scanId="scan-123"
                    scanType="single"
                    scanSourceUrl="https://acme.com"
                />
            )
            expect(screen.queryByText(/Part of:/)).not.toBeInTheDocument()
            // Only the Dashboard breadcrumb should be present, no portfolio link
            const portfolioLinks = screen.queryAllByRole('link', { name: /portfolio/i })
            expect(portfolioLinks).toHaveLength(0)
        })

        it('does not render provenance when scanId is absent', () => {
            render(<AnalysisHeader analysisId="test-id" companyName="Acme Corp" tier="high" />)
            expect(screen.queryByText(/Part of:/)).not.toBeInTheDocument()
        })

        it('falls back to "portfolio scan" label when scanSourceUrl is empty', () => {
            render(
                <AnalysisHeader
                    analysisId="test-id"
                    companyName="Acme Corp"
                    tier="high"
                    scanId="scan-123"
                    scanType="portfolio"
                />
            )
            expect(screen.getByText(/Part of:/)).toBeInTheDocument()
            expect(screen.getAllByText('portfolio scan').length).toBeGreaterThan(0)
        })

        it('strips https:// and trailing slash from scan URL label', () => {
            render(
                <AnalysisHeader
                    analysisId="test-id"
                    companyName="Acme Corp"
                    tier="high"
                    scanId="scan-123"
                    scanType="portfolio"
                    scanSourceUrl="https://www.example.com/firms/123/"
                />
            )
            expect(screen.queryByText(/https:/)).not.toBeInTheDocument()
            expect(screen.getAllByText('www.example.com/firms/123').length).toBeGreaterThan(0)
        })
    })
})
