import { render, screen, fireEvent, within } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
    usePathname: () => '/analyses',
}))

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: { user: { name: 'Test' } } }),
    signOut: vi.fn(),
}))

import AnalysesTable from '@/components/AnalysesTable'
import type { AnalysisItem } from '@/lib/types/api'

const mockAnalyses: AnalysisItem[] = [
    {
        id: '1',
        companyName: 'Acme Corp',
        companyUrl: 'https://acme.com',
        industry: 'SaaS',
        overallRiskScore: 8.5,
        riskTier: 'critical',
        analyzedAt: '2026-03-20T00:00:00Z',
        scanType: 'portfolio',
        scanId: 'scan-port-1',
    },
    {
        id: '2',
        companyName: 'Beta Inc',
        companyUrl: 'https://beta.com',
        industry: 'Fintech',
        overallRiskScore: 4.2,
        riskTier: 'moderate',
        analyzedAt: '2026-03-22T00:00:00Z',
        scanType: 'standalone',
        scanId: 'scan-single-1',
    },
    {
        id: '3',
        companyName: 'Gamma LLC',
        companyUrl: 'https://gamma.com',
        industry: 'Healthcare',
        overallRiskScore: 6.8,
        riskTier: 'high',
        analyzedAt: '2026-03-18T00:00:00Z',
        scanType: 'portfolio',
        scanId: 'scan-port-2',
    },
]

describe('AnalysesTable', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders all analyses', () => {
        render(<AnalysesTable analyses={mockAnalyses} />)
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
        expect(screen.getByText('Beta Inc')).toBeInTheDocument()
        expect(screen.getByText('Gamma LLC')).toBeInTheDocument()
    })

    it('shows result count', () => {
        render(<AnalysesTable analyses={mockAnalyses} />)
        expect(screen.getByText('3 analyses')).toBeInTheDocument()
    })

    it('renders search input', () => {
        render(<AnalysesTable analyses={mockAnalyses} />)
        expect(screen.getByLabelText('Search analyses')).toBeInTheDocument()
    })

    describe('search', () => {
        it('filters by company name', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'Acme' },
            })
            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.queryByText('Beta Inc')).not.toBeInTheDocument()
            expect(screen.getByText('1 of 3')).toBeInTheDocument()
        })

        it('filters by industry', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'fintech' },
            })
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
            expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument()
        })

        it('shows empty state when no matches', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'zzzzz' },
            })
            expect(screen.getByText('No analyses match your filters.')).toBeInTheDocument()
        })
    })

    describe('tier filter', () => {
        function getFilterChip(label: string) {
            // Filter chips have aria-pressed attribute; table badges don't
            const buttons = screen.getAllByText(label)
            const chip = buttons.find((el) => el.closest('[aria-pressed]'))
            if (!chip) throw new Error(`Filter chip "${label}" not found`)
            return chip
        }

        it('filters by risk tier when chip is clicked', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getFilterChip('Critical Risk'))
            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.queryByText('Beta Inc')).not.toBeInTheDocument()
            expect(screen.queryByText('Gamma LLC')).not.toBeInTheDocument()
        })

        it('clears tier filter when same chip clicked again', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getFilterChip('Critical Risk'))
            expect(screen.queryByText('Beta Inc')).not.toBeInTheDocument()

            fireEvent.click(getFilterChip('Critical Risk'))
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
        })
    })

    describe('combined filters', () => {
        function getFilterChip(label: string) {
            const buttons = screen.getAllByText(label)
            const chip = buttons.find((el) => el.closest('[aria-pressed]'))
            if (!chip) throw new Error(`Filter chip "${label}" not found`)
            return chip
        }

        it('search + tier filter combines with AND logic', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'Acme' },
            })
            fireEvent.click(getFilterChip('Critical Risk'))

            // Acme is critical — should still show
            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.getByText('1 of 3')).toBeInTheDocument()
        })

        it('search + tier filter hides non-matching', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'Acme' },
            })
            fireEvent.click(getFilterChip('Low Risk'))

            // Acme is critical, not low — should show empty
            expect(screen.getByText('No analyses match your filters.')).toBeInTheDocument()
        })
    })

    describe('type filter', () => {
        function getTypeChip(label: string) {
            const buttons = screen.getAllByText(label)
            const chip = buttons.find((el) => el.closest('[aria-pressed]'))
            if (!chip) throw new Error(`Type chip "${label}" not found`)
            return chip
        }

        it('filters by scan type', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getTypeChip('Standalone'))
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
            expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument()
        })
    })

    describe('sort', () => {
        it('sorts by company name when column header clicked', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(screen.getByLabelText('Sort by Company'))

            const rows = screen.getAllByRole('row')
            // Header + 3 data rows; first data row should be Acme (ascending)
            expect(rows[1]).toHaveTextContent('Acme Corp')
        })

        it('toggles sort direction on second click', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(screen.getByLabelText('Sort by Company'))
            fireEvent.click(screen.getByLabelText('Sort by Company'))

            const rows = screen.getAllByRole('row')
            // Descending: Gamma should be first
            expect(rows[1]).toHaveTextContent('Gamma LLC')
        })

        it('sorts by risk score', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(screen.getByLabelText('Sort by Risk Score'))

            // Default desc for risk score — highest first (8.5 = Acme)
            const rows = screen.getAllByRole('row')
            expect(rows[1]).toHaveTextContent('Acme Corp')
        })
    })

    describe('clear filters', () => {
        function getFilterChip(label: string) {
            const buttons = screen.getAllByText(label)
            const chip = buttons.find((el) => el.closest('[aria-pressed]'))
            if (!chip) throw new Error(`Filter chip "${label}" not found`)
            return chip
        }

        it('shows clear button when filters are active', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            expect(screen.queryByText('Clear all filters')).not.toBeInTheDocument()

            fireEvent.click(getFilterChip('Critical Risk'))
            expect(screen.getByText('Clear all filters')).toBeInTheDocument()
        })

        it('clears all filters when clicked', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getFilterChip('Critical Risk'))

            fireEvent.click(screen.getByText('Clear all filters'))

            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
            expect(screen.getByText('Gamma LLC')).toBeInTheDocument()
        })
    })

    it('shows empty state with CTA when no analyses exist', () => {
        render(<AnalysesTable analyses={[]} />)
        expect(screen.getByText('No analyses yet. Run your first scan to get started.')).toBeInTheDocument()
        expect(screen.getByText('Start a Scan')).toBeInTheDocument()
    })

    describe('scan-type badge navigation', () => {
        // Asserts on the rendered <a href>, not just text — the failure-mode
        // that #182's failed-card regression had was tests checking only text.
        // Use `within(table)` so we don't accidentally match the toolbar's
        // "Portfolio" filter chip.
        function getBadgeInTable(label: 'Portfolio' | 'Standalone'): HTMLElement {
            const table = screen.getByRole('table')
            return within(table).getByText(label)
        }

        it('Portfolio badge wraps in a link to /portfolio/{scanId}', () => {
            render(<AnalysesTable analyses={[mockAnalyses[0]]} />)
            const link = getBadgeInTable('Portfolio').closest('a')
            expect(link).not.toBeNull()
            expect(link).toHaveAttribute('href', '/portfolio/scan-port-1')
        })

        it('Standalone badge is plain text (no link)', () => {
            render(<AnalysesTable analyses={[mockAnalyses[1]]} />)
            expect(getBadgeInTable('Standalone').closest('a')).toBeNull()
        })

        it('Portfolio badge renders without link when scanId is missing (legacy data)', () => {
            // Defensive: a portfolio analysis missing scanId in older data
            // should not crash and should not produce a broken link.
            const legacyPortfolio: AnalysisItem = { ...mockAnalyses[0], scanId: undefined }
            render(<AnalysesTable analyses={[legacyPortfolio]} />)
            expect(getBadgeInTable('Portfolio').closest('a')).toBeNull()
        })

        it('Each portfolio row links to its own scan', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            const table = screen.getByRole('table')
            const allBadges = within(table).getAllByText('Portfolio')
            expect(allBadges).toHaveLength(2)
            const hrefs = allBadges.map((badge) => badge.closest('a')?.getAttribute('href'))
            expect(hrefs).toEqual(['/portfolio/scan-port-1', '/portfolio/scan-port-2'])
        })
    })
})
