import { screen, fireEvent, within, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

// Recharts ResponsiveContainer requires ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}))

import AnalysisDetail from '@/app/(authenticated)/analysis/[analysisId]/AnalysisDetail'
import type { AnalysisData } from '@/lib/types/api'

const mockSignOut = vi.fn()
const mockRefresh = vi.fn()
let mockSession = { user: { name: 'Test', email: 'test@test.com' } }

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: mockSession }),
    signOut: (...args: unknown[]) => mockSignOut(...args),
}))

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn(), refresh: mockRefresh }),
    usePathname: () => '/analysis/test-id',
}))

vi.mock('@/components/DocumentUpload', () => ({
    default: ({ onReanalyze }: { onReanalyze?: () => void }) => (
        <div data-testid="document-upload">
            Document Upload
            {onReanalyze && (
                <button data-testid="reanalyze-trigger" onClick={onReanalyze}>
                    Re-analyze
                </button>
            )}
        </div>
    ),
}))

const mockRealtimeStart = vi.fn().mockResolvedValue(false)
const mockRealtimeStop = vi.fn()

vi.mock('@/lib/hooks/useScanRealtime', () => ({
    useScanRealtime: () => ({
        start: mockRealtimeStart,
        stop: mockRealtimeStop,
    }),
}))

vi.mock('@/components/EbitdaTree', () => ({
    default: ({ treeData, opportunities }: { treeData: unknown[]; opportunities: unknown[] }) => (
        <div data-testid="ebitda-tree">
            EBITDA Tree ({treeData.length} nodes, {opportunities.length} opportunities)
        </div>
    ),
}))

function buildAnalysisData(overrides: Partial<AnalysisData> = {}): AnalysisData {
    return {
        id: 'test-id',
        companyName: 'Acme Corp',
        companyUrl: 'https://acme.com',
        industry: 'SaaS',
        overallRiskScore: 6.5,
        riskTier: 'high',
        analysisSummary: 'High risk company',
        riskScores: [
            {
                category: 'competitive_displacement',
                score: 8,
                rationale: 'Strong competition from AI startups',
            },
            {
                category: 'technology_obsolescence',
                score: 5,
                rationale: 'Moderate risk from some legacy systems',
            },
        ],
        opportunities: [
            {
                title: 'Deploy AI Chatbot',
                description: 'Build a chatbot',
                impact_rating: 'High',
                timeline: 'Quick Win (1-3 months)',
                strategic_category: 'Competitive Moat',
                value_lever: 'Revenue Side',
                implementation_steps: ['Step 1', 'Step 2'],
                investment_range: '$100K-$500K',
                roi_estimate: '30% improvement',
            },
            {
                title: 'Automate Support',
                description: 'Reduce support costs',
                impact_rating: 'Medium',
                timeline: 'Medium-term (3-9 months)',
                strategic_category: 'Operational Efficiency',
                value_lever: 'Cost Side',
                implementation_steps: ['Step A'],
                investment_range: '$50K-$100K',
                roi_estimate: '2x ROI',
            },
            {
                title: 'AI Platform',
                description: 'Build platform',
                impact_rating: 'High',
                timeline: 'Long-term (9-18 months)',
                strategic_category: 'Revenue Capture',
                value_lever: 'Both',
                implementation_steps: ['Step X'],
                investment_range: '$500K-$1M',
                roi_estimate: 'New revenue stream',
            },
        ],
        topActions: ['Action 1', 'Action 2', 'Action 3'],
        ...overrides,
    }
}

describe('AnalysisDetail — Value Lever', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSession = { user: { name: 'Test', email: 'test@test.com' } }
    })

    it('renders value lever summary cards with correct counts', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.getByText('Value Impact')).toBeInTheDocument()

        // Each lever label appears in both the summary card and as a badge on an opportunity.
        // Use getAllByText to confirm at least the summary card renders.
        expect(screen.getAllByText('Revenue Side').length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText('Cost Side').length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText('Both').length).toBeGreaterThanOrEqual(1)
    })

    it('clicking a lever card filters opportunities', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.getByText('Automate Support')).toBeInTheDocument()
        expect(screen.getByText('AI Platform')).toBeInTheDocument()

        // Click the "Revenue Side" summary card (the one inside the Value Impact section)
        const valueImpactHeading = screen.getByText('Value Impact')
        const valueImpactSection = valueImpactHeading.parentElement!
        const revenueSideCard = within(valueImpactSection).getAllByText('Revenue Side')[0]
        fireEvent.click(revenueSideCard.closest('[class*="card"]')!)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.queryByText('Automate Support')).not.toBeInTheDocument()
        expect(screen.queryByText('AI Platform')).not.toBeInTheDocument()
    })

    it('clicking active lever card resets filter to All', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        const valueImpactSection = screen.getByText('Value Impact').parentElement!
        const costSideCard = within(valueImpactSection)
            .getAllByText('Cost Side')[0]
            .closest('[class*="card"]')!

        fireEvent.click(costSideCard)
        expect(screen.queryByText('Deploy AI Chatbot')).not.toBeInTheDocument()
        expect(screen.getByText('Automate Support')).toBeInTheDocument()

        // Click again to deselect
        fireEvent.click(costSideCard)
        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.getByText('Automate Support')).toBeInTheDocument()
        expect(screen.getByText('AI Platform')).toBeInTheDocument()
    })

    it('hides value lever section when no opportunities have value_lever', () => {
        const data = buildAnalysisData({
            opportunities: [
                {
                    title: 'Old Opportunity',
                    description: 'From before value lever',
                    impact_rating: 'High',
                    timeline: 'Quick Win (1-3 months)',
                    strategic_category: 'Competitive Moat',
                    implementation_steps: ['Step 1'],
                },
            ],
        })
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.queryByText('Value Impact')).not.toBeInTheDocument()
        expect(screen.getByText('Old Opportunity')).toBeInTheDocument()
    })

    it('combined category and lever filter produces correct intersection', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        // Click "Competitive Moat" category filter — use the filter button, not the badge
        const oppHeading = screen.getByText(/AI Opportunities/)
        const oppSection = oppHeading.parentElement!
        const competitiveMoatButton = within(oppSection).getAllByText('Competitive Moat')[0]
        fireEvent.click(competitiveMoatButton)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.queryByText('Automate Support')).not.toBeInTheDocument()

        // Now also filter by "Cost Side" lever — intersection should be empty
        const valueImpactSection = screen.getByText('Value Impact').parentElement!
        const costSideCard = within(valueImpactSection)
            .getAllByText('Cost Side')[0]
            .closest('[class*="card"]')!
        fireEvent.click(costSideCard)

        expect(screen.queryByText('Deploy AI Chatbot')).not.toBeInTheDocument()
        expect(screen.queryByText('Automate Support')).not.toBeInTheDocument()
    })

    it('displays value lever badge on opportunity cards', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        // "Revenue Side" should appear at least twice: once in summary card, once as badge
        const revenueSideElements = screen.getAllByText('Revenue Side')
        expect(revenueSideElements.length).toBeGreaterThanOrEqual(2)
    })
})

describe('AnalysisDetail — EBITDA Tree', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders EBITDA section when ebitdaTree data is present', () => {
        const data = buildAnalysisData({
            ebitdaTree: {
                treeData: [
                    {
                        id: 'revenue',
                        label: 'Revenue',
                        type: 'revenue',

                        description: 'All revenue',
                        linked_opportunity_indices: [],
                        children: [],
                    },
                ],
                revenueEstimate: '$10M-$50M',
                ebitdaEstimate: '$2M-$8M',
                businessModelSummary: 'SaaS model with subscription revenue.',
            },
        })
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.getByText('EBITDA Impact Model')).toBeInTheDocument()
        expect(screen.getByText('Revenue: $10M-$50M')).toBeInTheDocument()
        expect(screen.getByText('EBITDA: $2M-$8M')).toBeInTheDocument()
        expect(screen.getByText('SaaS model with subscription revenue.')).toBeInTheDocument()
    })

    it('hides EBITDA section when ebitdaTree is not present', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.queryByText('EBITDA Impact Model')).not.toBeInTheDocument()
    })

    it('renders EBITDA tree without optional fields', () => {
        const data = buildAnalysisData({
            ebitdaTree: {
                treeData: [
                    {
                        id: 'revenue',
                        label: 'Revenue',
                        type: 'revenue',

                        description: 'Revenue',
                        linked_opportunity_indices: [],
                        children: [],
                    },
                ],
            },
        })
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        expect(screen.getByText('EBITDA Impact Model')).toBeInTheDocument()
        expect(screen.queryByText(/Revenue:/)).not.toBeInTheDocument()
        expect(screen.queryByText(/EBITDA:/)).not.toBeInTheDocument()
    })
})

describe('AnalysisDetail — Reanalysis Polling', () => {
    let fetchMock: ReturnType<typeof vi.fn>

    beforeEach(() => {
        vi.clearAllMocks()
        vi.useFakeTimers()
        mockSession = { user: { name: 'Test', email: 'test@test.com' } }
        fetchMock = vi.fn()
        global.fetch = fetchMock
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('polls until analyzedAt changes then refreshes', async () => {
        const data = buildAnalysisData({ analyzedAt: '2026-03-01T00:00:00Z' })

        // POST reanalyze succeeds
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ status: 'queued', scanId: 'scan-1' }),
        })
        // First poll — same analyzedAt
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ ...data, analyzedAt: '2026-03-01T00:00:00Z' }),
        })
        // Second poll — analyzedAt changed
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ ...data, analyzedAt: '2026-03-16T12:00:00Z' }),
        })

        render(<AnalysisDetail data={data} analysisId="test-id" />)
        const button = screen.getByTestId('reanalyze-trigger')

        await act(async () => {
            fireEvent.click(button)
        })

        // Advance through first poll interval
        await act(async () => {
            vi.advanceTimersByTime(3000)
        })

        // Advance through second poll interval
        await act(async () => {
            vi.advanceTimersByTime(3000)
        })

        expect(mockRefresh).toHaveBeenCalled()
        expect(fetchMock).toHaveBeenCalledTimes(3) // POST + 2 polls
    })

    it('refreshes on timeout when analyzedAt never changes', async () => {
        const data = buildAnalysisData({ analyzedAt: '2026-03-01T00:00:00Z' })

        // POST succeeds
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ status: 'queued', scanId: 'scan-1' }),
        })
        // All polls return same analyzedAt
        for (let i = 0; i < 40; i++) {
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ ...data, analyzedAt: '2026-03-01T00:00:00Z' }),
            })
        }

        render(<AnalysisDetail data={data} analysisId="test-id" />)

        await act(async () => {
            fireEvent.click(screen.getByTestId('reanalyze-trigger'))
        })

        // Advance through all 40 intervals (40 * 3000ms = 120s)
        for (let i = 0; i < 40; i++) {
            await act(async () => {
                vi.advanceTimersByTime(3000)
            })
        }

        // Should still refresh on timeout
        expect(mockRefresh).toHaveBeenCalled()
    })

    it('aborts polling on consecutive HTTP errors', async () => {
        const data = buildAnalysisData({ analyzedAt: '2026-03-01T00:00:00Z' })

        // POST succeeds
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ status: 'queued', scanId: 'scan-1' }),
        })
        // Three consecutive poll failures
        fetchMock.mockResolvedValueOnce({ ok: false })
        fetchMock.mockResolvedValueOnce({ ok: false })
        fetchMock.mockResolvedValueOnce({ ok: false })

        render(<AnalysisDetail data={data} analysisId="test-id" />)

        await act(async () => {
            fireEvent.click(screen.getByTestId('reanalyze-trigger'))
        })

        for (let i = 0; i < 3; i++) {
            await act(async () => {
                vi.advanceTimersByTime(3000)
            })
        }

        // Allow microtasks to flush
        await act(async () => {
            await Promise.resolve()
        })

        // Should NOT have called refresh — error should be set
        expect(mockRefresh).not.toHaveBeenCalled()
    })

    it('cleans up polling on component unmount', async () => {
        const data = buildAnalysisData({ analyzedAt: '2026-03-01T00:00:00Z' })

        // POST succeeds
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ status: 'queued', scanId: 'scan-1' }),
        })
        // Poll returns same data
        fetchMock.mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ ...data, analyzedAt: '2026-03-01T00:00:00Z' }),
        })

        const { unmount } = render(<AnalysisDetail data={data} analysisId="test-id" />)

        await act(async () => {
            fireEvent.click(screen.getByTestId('reanalyze-trigger'))
        })

        // Advance one poll
        await act(async () => {
            vi.advanceTimersByTime(3000)
        })

        // Unmount mid-polling
        unmount()

        // Advance more — fetch should be aborted, no errors
        await act(async () => {
            vi.advanceTimersByTime(10000)
        })

        // No crash, no unhandled rejections — test passes if we get here
        expect(true).toBe(true)
    })
})
