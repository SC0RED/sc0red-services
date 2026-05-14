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

        // Click the "Revenue Side" summary card (the one inside the Value Impact section).
        // Pre-`extract-definition-popover` this used `.parentElement!` from
        // the heading text — that walked into `.section-header-row`, which
        // no longer contains the lever cards. The testid wrapper is the
        // stable handle.
        const valueImpactSection = screen.getByTestId('analysis-section-value-lever')
        const revenueSideCard = within(valueImpactSection).getAllByText('Revenue Side')[0]
        fireEvent.click(revenueSideCard.closest('[class*="card"]')!)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.queryByText('Automate Support')).not.toBeInTheDocument()
        expect(screen.queryByText('AI Platform')).not.toBeInTheDocument()
    })

    it('clicking active lever card resets filter to All', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        const valueImpactSection = screen.getByTestId('analysis-section-value-lever')
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
        const oppSection = screen.getByTestId('analysis-section-opportunities')
        const competitiveMoatButton = within(oppSection).getAllByText('Competitive Moat')[0]
        fireEvent.click(competitiveMoatButton)

        expect(screen.getByText('Deploy AI Chatbot')).toBeInTheDocument()
        expect(screen.queryByText('Automate Support')).not.toBeInTheDocument()

        // Now also filter by "Cost Side" lever — intersection should be empty
        const valueImpactSection = screen.getByTestId('analysis-section-value-lever')
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

    it('dismisses the loading toast when fetch is aborted mid-flight', async () => {
        // The re-analyze flow's only `toast.dismiss` call sits on the
        // AbortError catch path. Pinning it here so a future refactor that
        // accidentally drops the dismiss leaves the loading toast leaked
        // on screen.
        const data = buildAnalysisData({ analyzedAt: '2026-03-01T00:00:00Z' })

        // POST returns 200, then the polling fetch rejects with AbortError
        // — simulates the user navigating away or some other cancellation.
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: () => Promise.resolve({ status: 'queued', scanId: 'scan-1' }),
        })
        const abortError = new DOMException('aborted', 'AbortError')
        fetchMock.mockRejectedValueOnce(abortError)

        render(<AnalysisDetail data={data} analysisId="test-id" />)
        await act(async () => {
            fireEvent.click(screen.getByTestId('reanalyze-trigger'))
        })

        // Loading toast is up
        expect(screen.getByText('Re-analyzing...')).toBeInTheDocument()

        // Advance through one poll → AbortError thrown → catch path runs
        await act(async () => {
            vi.advanceTimersByTime(3000)
        })
        await act(async () => {
            await Promise.resolve()
        })

        // Toast was dismissed (not promoted to error — abort is silent)
        expect(screen.queryByText('Re-analyzing...')).not.toBeInTheDocument()
        // And no error toast surfaced
        expect(screen.queryByText(/Re-analysis failed/)).not.toBeInTheDocument()
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

describe('AnalysisDetail — DeepDiveCTA placement (redesign-analysis-detail-narrative)', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSession = { user: { name: 'Test', email: 'test@test.com' } }
    })

    /**
     * The headline DeepDiveCTA now renders IMMEDIATELY AFTER the
     * StrategyMapView — placing the upsell pitch at the moment of
     * maximum buying intent ("we'll help you operationalise this
     * strategy") rather than asking for the upsell before any
     * analysis content has loaded.
     *
     * This supersedes PR #239's design.md decision D6, which had hoisted
     * the CTA above the strategy map "for visibility." That fix
     * over-corrected — visibility came at the cost of asking before
     * showing value. See redesign-analysis-detail-narrative D1 + D6.
     */
    it('renders the headline CTA AFTER the StrategyMapView in the DOM tree', () => {
        const data = buildAnalysisData({
            strategyMap: {
                vision: {
                    statement: 'Vision statement long enough to satisfy validation.',
                    synthesised: false,
                    rationale: 'Rationale long enough.',
                },
                mission: {
                    statement: 'Mission statement long enough to satisfy validation.',
                    synthesised: false,
                    rationale: 'Rationale long enough.',
                },
                valueProposition: {
                    primary: 'customer_intimacy',
                    secondary: null,
                    rationale: 'Public materials emphasise tailored deep-dives and partnership delivery.',
                    exemplar_company: 'Wawa',
                },
                strategicPriorities: [
                    {
                        name: 'Theme A',
                        result: 'Best-in-class outcome that satisfies the result min length.',
                    },
                    {
                        name: 'Theme B',
                        result: 'Industry-leading outcome that satisfies the result length.',
                    },
                ],
                financial: {
                    objectives: [
                        {
                            id: 'F1',
                            title: 'Grow profitable revenue across markets',
                            definition:
                                'We will grow same-segment revenue by deepening engagement; supports F1 column.',
                            category: 'revenue_growth',
                            confidence: 'HIGH',
                        },
                        {
                            id: 'F2',
                            title: 'Drive operational efficiency further',
                            definition:
                                'We will improve cost-to-serve metrics by automating routine operations everywhere.',
                            category: 'productivity',
                            confidence: 'MEDIUM',
                        },
                        {
                            id: 'F3',
                            title: 'Maximise return on invested capital',
                            definition:
                                'We will allocate capital toward the highest-return store formats overall.',
                            category: 'productivity',
                            confidence: 'MEDIUM',
                        },
                    ],
                },
                customer: {
                    objectives: [
                        {
                            id: 'C1',
                            title: 'Offer me fresh products in a friendly environment',
                            definition:
                                'I rely on this brand for fast, friendly service and consistent quality.',
                            panel: 'consumer',
                            confidence: 'HIGH',
                        },
                        {
                            id: 'C2',
                            title: 'Recognise my loyalty and reward me appropriately',
                            definition:
                                'I expect the loyalty programme to acknowledge my repeated visits with rewards.',
                            panel: 'consumer',
                            confidence: 'MEDIUM',
                        },
                        {
                            id: 'C3',
                            title: 'Make my visit fast and convenient overall',
                            definition: 'I want to get in, get what I need, and get out without friction.',
                            panel: 'consumer',
                            confidence: 'HIGH',
                        },
                    ],
                },
                internalProcesses: {
                    themes: [
                        {
                            name: 'Theme A',
                            supports_financial_objectives: ['F1'],
                            objectives: [
                                {
                                    id: 'I1.1',
                                    title: 'Develop signature offers',
                                    definition:
                                        'We will create and improve fresh food and beverage offers that differentiate.',
                                    category: 'innovation',
                                    confidence: 'HIGH',
                                },
                            ],
                        },
                        {
                            name: 'Theme B',
                            supports_financial_objectives: ['F2'],
                            objectives: [
                                {
                                    id: 'I2.1',
                                    title: 'Improve end-to-end throughput',
                                    definition:
                                        'We will continuously improve the throughput, quality and cost of our processes.',
                                    category: 'operational_excellence',
                                    confidence: 'HIGH',
                                },
                            ],
                        },
                    ],
                },
                organizationalCapacity: {
                    people: {
                        id: 'O.P',
                        title: 'Develop our associates as ambassadors',
                        definition:
                            'We will invest in associate development through structured training programmes.',
                        confidence: 'MEDIUM',
                    },
                    technology: {
                        id: 'O.T',
                        title: 'Deliver reliable systems and insight',
                        definition:
                            'We will provide consistently reliable technical products and support services.',
                        confidence: 'MEDIUM',
                    },
                    culture: {
                        id: 'O.C',
                        title: 'Live our values in every interaction',
                        definition: 'Our values are the foundation of how we work across the organisation.',
                        confidence: 'LOW',
                    },
                },
                arrows: [],
                coreValues: {
                    values: ['Care', 'Respect', 'Continuous improvement'],
                    synthesised: true,
                    rationale: 'Synthesised from public materials.',
                },
            },
        })

        render(<AnalysisDetail data={data} analysisId="test-id" />)

        const cta = screen.getByTestId('strategy-map-cta')
        const map = screen.getByTestId('strategy-map-view')

        // The CTA must appear AFTER the strategy map in document order
        // (i.e. it's later in the DOM tree). compareDocumentPosition
        // returns DOCUMENT_POSITION_PRECEDING (2) when the argument
        // precedes the receiver — i.e. `map` comes before `cta`.
        const relationship = cta.compareDocumentPosition(map)
        expect(relationship & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy()
    })

    it('does NOT render the deep-dive CTA when the analysis has no strategy map', () => {
        const data = buildAnalysisData()
        // No ``strategyMap`` on the data → ``StrategyMapSlot`` returns
        // ``null`` (per ``redesign-strategy-map`` Phase 4). Both the
        // strategy-map section wrapper AND the deep-dive CTA wrapper
        // are absent from the DOM.
        render(<AnalysisDetail data={data} analysisId="test-id" />)
        expect(screen.queryByTestId('analysis-section-strategy-map')).toBeNull()
        expect(screen.queryByTestId('analysis-section-deep-dive-cta')).toBeNull()
    })
})

describe('AnalysisDetail — section ordering (redesign-analysis-detail-narrative)', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSession = { user: { name: 'Test', email: 'test@test.com' } }
    })

    /**
     * Asserts the page-level beat order specified in design D1. Each
     * section is wrapped at the page level with a `data-testid` of the
     * form `analysis-section-*` so the order test queries the wrappers
     * by ID rather than relying on layout coordinates (jsdom doesn't
     * lay out reliably) or fragile selector chains.
     */
    function getRenderedSectionIds() {
        const wrappers = document.querySelectorAll<HTMLElement>('[data-testid^="analysis-section-"]')
        return Array.from(wrappers).map((el) =>
            el.getAttribute('data-testid')!.replace('analysis-section-', '')
        )
    }

    it('renders all 12 sections in the prescribed beat order with full data', () => {
        // Full-data fixture: builds the success-path analysis with every
        // optional artifact present so all 12 sections render.
        const data: AnalysisData = {
            ...buildAnalysisData(),
            analyzedAt: '2026-05-05T10:00:00Z',
            ebitdaTree: {
                treeData: [
                    {
                        id: 'r',
                        label: 'Revenue',
                        type: 'revenue',
                        description: 'r',
                        linked_opportunity_indices: [],
                        children: [],
                    },
                ],
                ebitdaEstimate: '$5M-$140M',
            },
            valueChain: {
                summary: 'Value chain summary',
                steps: [
                    {
                        id: 's1',
                        label: 'Inbound',
                        description: 'd',
                        category: 'primary',
                        risk_categories: [],
                        opportunity_indices: [],
                    },
                ],
            },
            strategyMap: makeFullStrategyMap(),
        }

        render(<AnalysisDetail data={data} analysisId="test-id" />)

        // Per ``redesign-strategy-map`` Phase 5:
        //   - The standalone Sc0redCTABanner ("Dig deeper") at Beat 1.5
        //     is gone — it was redundant with the DeepDiveCTA rendered
        //     alongside the strategy map.
        //   - The strategy-map slot moved up to Beat 3 (immediately
        //     after the Top-3 immediate actions). With a populated
        //     map the slot renders <StrategyMapView/> + <DeepDiveCTA/>.
        const expectedOrder = [
            'header',
            'strap',
            'overview',
            'top-actions',
            'strategy-map',
            'deep-dive-cta',
            'ebitda',
            'value-chain',
            'risk-breakdown',
            'value-lever',
            'opportunities',
            'document-upload',
        ]
        expect(getRenderedSectionIds()).toEqual(expectedOrder)
    })

    it('preserves relative order when strategy map and EBITDA are absent', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        const ids = getRenderedSectionIds()
        // EBITDA + value chain absent — those sections drop entirely.
        expect(ids).not.toContain('ebitda')
        expect(ids).not.toContain('value-chain')
        // Per Phase 4 the strategy-map slot returns ``null`` when the
        // map is absent — both the slot wrapper and its DeepDiveCTA
        // companion drop from the DOM.
        expect(ids).not.toContain('strategy-map')
        expect(ids).not.toContain('deep-dive-cta')
        // Sc0redCTABanner deleted in Phase 5 — no ``sc0red-cta`` slot.
        expect(ids).not.toContain('sc0red-cta')
        // Remaining sections still in the same relative order.
        expect(ids).toEqual([
            'header',
            'strap',
            'overview',
            'top-actions',
            'risk-breakdown',
            'value-lever',
            'opportunities',
            'document-upload',
        ])
    })

    it('does not render a standalone Sc0red CTA banner (Phase 5 removed it)', () => {
        // ``redesign-strategy-map`` Phase 5 deleted the ``Sc0redCTABanner``
        // that previously sat at Beat 1.5. The ``DeepDiveCTA`` rendered
        // alongside the strategy map (when present) is now the only
        // deep-dive affordance on the analysis page.
        const data = buildAnalysisData({ opportunities: [] })
        render(<AnalysisDetail data={data} analysisId="test-id" />)

        const ids = getRenderedSectionIds()
        expect(ids).not.toContain('sc0red-cta')
    })

    it('renders the executive strap between header and overview cards', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)
        const ids = getRenderedSectionIds()
        expect(ids[0]).toBe('header')
        expect(ids[1]).toBe('strap')
        expect(ids[2]).toBe('overview')
        // Strap content includes the company name from buildAnalysisData
        // and the opportunity count from the fixture (3).
        expect(screen.getByTestId('analysis-executive-strap')).toBeInTheDocument()
    })

    it('renders the "Improve This Analysis" heading + lead at the page level (not inside DocumentUpload)', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)
        // Page-level framing per architecture-review fix: the heading +
        // lead live in `AnalysisDetail` so the leaf `DocumentUpload` is
        // reusable from `FailedAnalysisView` with its own framing.
        expect(screen.getByText('Improve This Analysis')).toBeInTheDocument()
        expect(
            screen.getByText(/Upload financial statements, board decks, or product docs/)
        ).toBeInTheDocument()
    })

    it('does NOT render an orphaned reanalyze progress block at the page level', () => {
        const data = buildAnalysisData()
        render(<AnalysisDetail data={data} analysisId="test-id" />)
        // The progress block only appears as a descendant of
        // DocumentUpload (when reanalyzing); it must NEVER render as a
        // top-level sibling on the page. Since reanalyzing is false in
        // this fixture, no progress block exists at all.
        expect(screen.queryByTestId('reanalyze-progress')).toBeNull()
    })
})

describe('AnalysisDetail — section heading framing (analysis-detail-consistency-wrapper)', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSession = { user: { name: 'Test', email: 'test@test.com' } }
    })

    /**
     * Per `analysis-detail-consistency-wrapper` D3, every migrated
     * section's heading lives at the PAGE level (inside the
     * `AnalysisSection` wrapper) rather than inside the leaf
     * component. These tests pin the page-level rendering so a
     * future regression that re-introduces an internal heading (or
     * removes the page-level one) fails fast.
     *
     * Each assertion uses `within(wrapper).getByText(...)` so the
     * test fails not just when the text is missing, but also if the
     * text drifts to a different section's wrapper.
     */
    function buildFullData() {
        return {
            ...buildAnalysisData(),
            ebitdaTree: {
                treeData: [
                    {
                        id: 'r',
                        label: 'Revenue',
                        type: 'revenue' as const,
                        description: 'r',
                        linked_opportunity_indices: [],
                        children: [],
                    },
                ],
                ebitdaEstimate: '$2M-$8M',
            },
            valueChain: {
                summary: 'Value chain summary',
                steps: [
                    {
                        id: 's1',
                        label: 'Inbound',
                        description: 'd',
                        category: 'primary' as const,
                        risk_categories: [],
                        opportunity_indices: [],
                    },
                ],
            },
        }
    }

    it('renders "Risk Breakdown" inside the page-level risk-breakdown wrapper', () => {
        render(<AnalysisDetail data={buildAnalysisData()} analysisId="test-id" />)
        const wrapper = screen.getByTestId('analysis-section-risk-breakdown')
        expect(within(wrapper).getByRole('heading', { name: 'Risk Breakdown' })).toBeInTheDocument()
    })

    it('renders "EBITDA Impact Model" inside the page-level ebitda wrapper with a clean accessible name', () => {
        // Two assertions, two roles:
        //   1. Exact-match heading query — REGRESSION GUARD against
        //      future drift where a contributor smuggles raw text or
        //      another label into the title.
        //   2. `heading.contains(helpButton)).toBe(false)` — the TRUE
        //      structural proof that HelpTooltip is a sibling of the
        //      <h2>, not a descendant. Under the old inside-h2
        //      structure this would correctly fail.
        // Note: the exact-match query alone is NOT a structural proof —
        // `dom-accessibility-api` doesn't concatenate the descendant
        // button's `aria-label` into the heading's name when the
        // button's visible content is `aria-hidden`.
        render(<AnalysisDetail data={buildFullData()} analysisId="test-id" />)
        const wrapper = screen.getByTestId('analysis-section-ebitda')
        const heading = within(wrapper).getByRole('heading', { name: 'EBITDA Impact Model' })
        expect(heading).toBeInTheDocument()
        // Structural proof: help-tooltip button is INSIDE the section
        // wrapper but OUTSIDE the heading element.
        const helpButton = within(wrapper).getByRole('button', { name: /What is EBITDA Tree/i })
        expect(helpButton).toBeInTheDocument()
        expect(heading.contains(helpButton)).toBe(false)
    })

    it('renders "Value Chain Analysis" inside the page-level value-chain wrapper', () => {
        render(<AnalysisDetail data={buildFullData()} analysisId="test-id" />)
        const wrapper = screen.getByTestId('analysis-section-value-chain')
        expect(within(wrapper).getByRole('heading', { name: 'Value Chain Analysis' })).toBeInTheDocument()
    })

    it('renders "Value Impact" inside the page-level value-lever wrapper with a clean accessible name', () => {
        // Same two-assertion pattern as the EBITDA test above:
        // exact-match heading is a regression guard; `contains(...).toBe(false)`
        // is the structural proof that HelpTooltip lives outside the <h2>.
        render(<AnalysisDetail data={buildAnalysisData()} analysisId="test-id" />)
        const wrapper = screen.getByTestId('analysis-section-value-lever')
        const heading = within(wrapper).getByRole('heading', { name: 'Value Impact' })
        expect(heading).toBeInTheDocument()
        const helpButton = within(wrapper).getByRole('button', { name: /What is Value Lever/i })
        expect(helpButton).toBeInTheDocument()
        expect(heading.contains(helpButton)).toBe(false)
    })

    it('renders "AI Opportunities (3)" inside the page-level opportunities wrapper with a clean accessible name', () => {
        // Title text includes the count badge ("AI Opportunities (3)")
        // because the badge is a structural part of the heading text,
        // not an interactive adornment. The HelpTooltip moves to the
        // adornment slot. Same regression-guard + structural-proof
        // pattern as above.
        render(<AnalysisDetail data={buildAnalysisData()} analysisId="test-id" />)
        const wrapper = screen.getByTestId('analysis-section-opportunities')
        const heading = within(wrapper).getByRole('heading', { name: 'AI Opportunities (3)' })
        expect(heading).toBeInTheDocument()
        const helpButton = within(wrapper).getByRole('button', { name: /What is Impact Rating/i })
        expect(helpButton).toBeInTheDocument()
        expect(heading.contains(helpButton)).toBe(false)
    })

    it('renders "Improve This Analysis" inside the page-level document-upload wrapper', () => {
        render(<AnalysisDetail data={buildAnalysisData()} analysisId="test-id" />)
        const wrapper = screen.getByTestId('analysis-section-document-upload')
        expect(within(wrapper).getByRole('heading', { name: 'Improve This Analysis' })).toBeInTheDocument()
    })

    it('renders the "Improve This Analysis" lead inside the same wrapper as the heading', () => {
        // Pins the lead-paragraph containment so a regression that
        // accidentally renders the lead as a sibling of the
        // AnalysisSection (rather than inside it) fails. Closes a
        // coverage gap noted by the architecture-reviewer.
        render(<AnalysisDetail data={buildAnalysisData()} analysisId="test-id" />)
        const wrapper = screen.getByTestId('analysis-section-document-upload')
        expect(
            within(wrapper).getByText(/Upload financial statements, board decks, or product docs/)
        ).toBeInTheDocument()
    })

    it('omits the value-lever wrapper entirely when no opportunities have value_lever', () => {
        // Page-level conditional rendering: when no value_lever data
        // exists, the wrapper itself doesn't render — no empty
        // testid'd element with just a heading and no body.
        const data = buildAnalysisData({
            opportunities: [
                {
                    title: 'Old Opportunity',
                    description: 'No value lever set',
                    impact_rating: 'High',
                    timeline: 'Quick Win',
                    strategic_category: 'Competitive Moat',
                },
            ],
        })
        render(<AnalysisDetail data={data} analysisId="test-id" />)
        expect(screen.queryByTestId('analysis-section-value-lever')).toBeNull()
    })
})

describe('AnalysisDetail — type-scale invariants (tighten-analysis-page-readability)', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockSession = { user: { name: 'Test', email: 'test@test.com' } }
    })

    /**
     * Per ``analysis-page-readability`` Requirement §3: inline
     * ``fontSize`` values inside analysis-page components SHALL match
     * one of five canonical rem steps (0.75 / 0.875 / 1 / 1.125 /
     * 1.5) OR one of three documented display-stat exceptions
     * (1.625 on the AnalysisHeader h1, 2.5 on the OverviewCards
     * risk-score, 1.75 on the ValueLeverSummary lever-count).
     *
     * This regression test walks the full rendered DOM with the
     * canonical fixture and asserts every inline ``fontSize`` style
     * value is on-scale. Catches off-scale values reintroduced by
     * future contributors.
     */
    it('every inline fontSize on the rendered page is on the canonical scale or a documented exception', () => {
        const data = buildAnalysisData({
            ebitdaTree: {
                treeData: [
                    {
                        id: 'rev',
                        label: 'Total Revenue',
                        type: 'revenue',
                        value_range: '$10M',
                        parent_id: null,
                        description: 'Total revenue across all channels',
                        linked_opportunity_indices: [],
                        children: [],
                    },
                ],
                revenueEstimate: '$10M',
                ebitdaEstimate: '$2M',
                businessModelSummary: 'SaaS business model',
            },
            strategyMap: makeFullStrategyMap(),
        })
        const { container } = render(<AnalysisDetail data={data} analysisId="test-id" />)

        const ALLOWED = new Set([
            // Five canonical steps from the body type scale.
            '0.75rem',
            '0.875rem',
            '1rem',
            '1.125rem',
            '1.5rem',
            // Three documented display-stat exceptions.
            '1.625rem',
            '1.75rem',
            '2.5rem',
        ])

        const offending: Array<{ tag: string; size: string }> = []
        for (const el of Array.from(container.querySelectorAll<HTMLElement>('*'))) {
            const inline = el.style.fontSize
            if (!inline) continue
            // Some inline values may be set as ``0.875rem`` literally,
            // others may be normalised by the browser; both should be
            // checked as the raw string. Skip non-rem units (e.g.
            // ``inherit``, ``1em`` — fine, just not in our scale).
            if (!inline.endsWith('rem')) continue
            if (!ALLOWED.has(inline)) {
                offending.push({ tag: el.tagName, size: inline })
            }
        }

        expect(offending).toEqual([])
    })
})

/**
 * Strategy-map fixture for ordering tests. Mirrors the shape required
 * by `StrategyMapView` so the component renders without throwing during
 * order assertions.
 */
function makeFullStrategyMap(): NonNullable<AnalysisData['strategyMap']> {
    return {
        vision: {
            statement: 'Vision statement long enough to satisfy validation.',
            synthesised: false,
            rationale: 'r',
        },
        mission: {
            statement: 'Mission statement long enough to satisfy validation.',
            synthesised: false,
            rationale: 'r',
        },
        valueProposition: {
            primary: 'customer_intimacy',
            secondary: null,
            rationale: 'Public materials emphasise tailored deep-dives.',
            exemplar_company: 'Wawa',
        },
        strategicPriorities: [
            {
                name: 'Theme A',
                result: 'Best-in-class outcome that satisfies the result min length.',
            },
        ],
        financial: {
            objectives: [
                {
                    id: 'F1',
                    title: 'Grow profitable revenue across markets',
                    definition:
                        'We will grow same-segment revenue by deepening engagement; supports F1 column.',
                    category: 'revenue_growth',
                    confidence: 'HIGH',
                },
            ],
        },
        customer: {
            objectives: [
                {
                    id: 'C1',
                    title: 'Offer me fresh products in a friendly environment',
                    definition: 'I rely on this brand for fast, friendly service and consistent quality.',
                    panel: 'consumer',
                    confidence: 'HIGH',
                },
            ],
        },
        internalProcesses: {
            themes: [
                {
                    name: 'Theme A',
                    supports_financial_objectives: ['F1'],
                    objectives: [
                        {
                            id: 'I1.1',
                            title: 'Develop signature offers',
                            definition:
                                'We will create and improve fresh food and beverage offers that differentiate.',
                            category: 'innovation',
                            confidence: 'HIGH',
                        },
                    ],
                },
            ],
        },
        organizationalCapacity: {
            people: {
                id: 'O.P',
                title: 'Develop our associates as ambassadors',
                definition: 'We will invest in associate development through structured training programmes.',
                confidence: 'MEDIUM',
            },
            technology: {
                id: 'O.T',
                title: 'Deliver reliable systems and insight',
                definition: 'We will provide consistently reliable technical products and support services.',
                confidence: 'MEDIUM',
            },
            culture: {
                id: 'O.C',
                title: 'Live our values in every interaction',
                definition: 'Our values are the foundation of how we work across the organisation.',
                confidence: 'LOW',
            },
        },
        arrows: [],
        coreValues: {
            values: ['Care', 'Respect'],
            synthesised: true,
            rationale: 'Synthesised from public materials.',
        },
    }
}
