import { render, screen, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import PortfolioView from '@/app/(authenticated)/portfolio/[scanId]/PortfolioView'
import type { ScanAnalysis } from '@/lib/types/api'

vi.mock('next/link', () => ({
    default: ({
        href,
        children,
        ...props
    }: {
        href: string
        children: React.ReactNode
        [key: string]: unknown
    }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}))

const doneAnalysis: ScanAnalysis = {
    id: 'a-1',
    companyName: 'Acme Corp',
    companyUrl: 'https://acme.com',
    industry: 'SaaS',
    overallRiskScore: 7.5,
    riskTier: 'high',
    error: null,
    analyzedAt: '2026-03-12T10:00:00Z',
    state: 'done',
    orderIndex: 0,
}

const pendingAnalysis: ScanAnalysis = {
    id: 'a-2',
    companyName: 'Beta Inc',
    companyUrl: 'https://beta.com',
    industry: '',
    overallRiskScore: null,
    riskTier: null,
    error: null,
    analyzedAt: null,
    state: 'pending',
    orderIndex: 1,
}

const scanningAnalysis: ScanAnalysis = {
    id: 'a-4',
    companyName: 'Delta LLC',
    companyUrl: 'https://delta.com',
    industry: '',
    overallRiskScore: null,
    riskTier: null,
    error: null,
    analyzedAt: null,
    pipelineProgress: 50,
    pipelineLabel: 'Profiling risk...',
    state: 'scanning',
    orderIndex: 2,
}

const failedAnalysis: ScanAnalysis = {
    id: 'a-3',
    companyName: 'Gamma Ltd',
    companyUrl: 'https://gamma.com',
    industry: '',
    overallRiskScore: null,
    riskTier: null,
    error: 'Pipeline failed',
    analyzedAt: null,
    state: 'failed',
    orderIndex: 3,
}

function makeScan(analyses: ScanAnalysis[], status = 'running', totalCompanies?: number) {
    return {
        status,
        progress: 50,
        type: 'portfolio',
        totalCompanies: totalCompanies ?? analyses.length,
        portfolioCompanies: [],
        analyses,
    }
}

describe('PortfolioView', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        global.fetch = vi.fn()
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.restoreAllMocks()
    })

    describe('state-driven card rendering', () => {
        it('renders DONE state with risk score and tier badge', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([doneAnalysis])} />
            )
            expect(screen.getAllByText('Acme Corp').length).toBeGreaterThan(0)
            expect(screen.getAllByText('7.5').length).toBeGreaterThan(0)
            expect(screen.getAllByText(/high risk/i).length).toBeGreaterThan(0)
            expect(container.querySelector('[data-state="done"]')).toBeInTheDocument()
        })

        it('renders PENDING state with quiet "Pending" affordance', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />
            )
            expect(screen.getAllByText('Pending').length).toBeGreaterThan(0)
            expect(container.querySelector('[data-state="pending"]')).toBeInTheDocument()
            // No pulse-dot for pending — only for scanning
            expect(container.querySelector('.pulse-dot')).not.toBeInTheDocument()
        })

        it('renders SCANNING state with pulsing dot + pipeline label', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([scanningAnalysis])} />
            )
            expect(screen.getAllByText('Profiling risk...').length).toBeGreaterThan(0)
            expect(container.querySelector('[data-state="scanning"]')).toBeInTheDocument()
            // Pulsing dot is present and aria-hidden (decorative)
            const dot = container.querySelector('.pulse-dot')
            expect(dot).toBeInTheDocument()
            expect(dot?.getAttribute('aria-hidden')).toBe('true')
        })

        it('renders SCANNING state with default label when pipelineLabel is empty', () => {
            const noLabelScanning = { ...scanningAnalysis, pipelineLabel: '' }
            render(<PortfolioView scanId="scan-1" initialScan={makeScan([noLabelScanning])} />)
            // Card uses fallback "Analyzing..." text
            expect(screen.getAllByText('Analyzing...').length).toBeGreaterThan(0)
        })

        it('renders FAILED state with company name and FAILED badge', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([failedAnalysis])} />
            )
            expect(screen.getAllByText('Gamma Ltd').length).toBeGreaterThan(0)
            expect(screen.getByText('FAILED')).toBeInTheDocument()
            expect(container.querySelector('[data-state="failed"]')).toBeInTheDocument()
        })

        it('renders FAILED state without company name as Unknown Company', () => {
            const noNameFailure = { ...failedAnalysis, companyName: '' }
            render(<PortfolioView scanId="scan-1" initialScan={makeScan([noNameFailure])} />)
            expect(screen.getAllByText('Unknown Company').length).toBeGreaterThan(0)
            expect(screen.getByText('FAILED')).toBeInTheDocument()
        })
    })

    describe('card navigation by state', () => {
        // Regression check: failed cards used to navigate to /analysis/{id}
        // before the state-driven rewrite. The `failed-analysis-detail` spec
        // requires this behavior so the user can read the error and re-analyze.
        // These assertions follow the rendered <a href> rather than text so a
        // future regression that drops the link can't slip through visually.
        function getCardLink(container: HTMLElement, dataState: string): HTMLAnchorElement | null {
            const card = container.querySelector(`.card[data-state="${dataState}"]`)
            return card?.closest('a') ?? null
        }

        it('DONE card links to /analysis/{id}', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([doneAnalysis])} />
            )
            const link = getCardLink(container, 'done')
            expect(link).not.toBeNull()
            expect(link?.getAttribute('href')).toBe(`/analysis/${doneAnalysis.id}`)
        })

        it('FAILED card links to /analysis/{id} (regression: do not break navigation)', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([failedAnalysis])} />
            )
            const link = getCardLink(container, 'failed')
            expect(link).not.toBeNull()
            expect(link?.getAttribute('href')).toBe(`/analysis/${failedAnalysis.id}`)
        })

        it('PENDING card href is #, not /analysis/...', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />
            )
            const link = getCardLink(container, 'pending')
            expect(link?.getAttribute('href')).toBe('#')
        })

        it('SCANNING card href is #, not /analysis/...', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([scanningAnalysis])} />
            )
            const link = getCardLink(container, 'scanning')
            expect(link?.getAttribute('href')).toBe('#')
        })

        it('FAILED row shows "View Error" link to /analysis/{id}', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([failedAnalysis])} />
            )
            const row = container.querySelector('tr[data-state="failed"]')
            expect(row).not.toBeNull()
            const link = row?.querySelector('a')
            expect(link?.textContent).toBe('View Error')
            expect(link?.getAttribute('href')).toBe(`/analysis/${failedAnalysis.id}`)
        })

        it('DONE row shows "View Report" link to /analysis/{id}', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([doneAnalysis])} />
            )
            const row = container.querySelector('tr[data-state="done"]')
            expect(row).not.toBeNull()
            const link = row?.querySelector('a')
            expect(link?.textContent).toBe('View Report')
            expect(link?.getAttribute('href')).toBe(`/analysis/${doneAnalysis.id}`)
        })

        it('PENDING row has no action link', () => {
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />
            )
            const row = container.querySelector('tr[data-state="pending"]')
            expect(row?.querySelector('a')).toBeNull()
        })
    })

    describe('all-cards-from-t=0 stability', () => {
        it('renders 50 pending cards immediately on first render', () => {
            const allPending = Array.from({ length: 50 }, (_, i) => ({
                ...pendingAnalysis,
                id: `id-${i}`,
                companyName: `Co ${i}`,
                orderIndex: i,
            }))
            const { container } = render(<PortfolioView scanId="scan-1" initialScan={makeScan(allPending)} />)
            // Heatmap and table both render — assert each surface independently
            // so a regression in one place doesn't disappear into a sum.
            const cardsPending = container.querySelectorAll('.card[data-state="pending"]')
            const rowsPending = container.querySelectorAll('tr[data-state="pending"]')
            expect(cardsPending.length).toBe(50)
            expect(rowsPending.length).toBe(50)
        })

        function getCardCompanyNames(container: HTMLElement): string[] {
            const cards = container.querySelectorAll('.card[data-state]')
            return Array.from(cards).map((el) => el.querySelector('.truncate')?.textContent ?? '')
        }

        it('renders cards in orderIndex ascending order', () => {
            const shuffled = [
                { ...pendingAnalysis, id: 'z', companyName: 'Z Co', orderIndex: 2 },
                { ...pendingAnalysis, id: 'a', companyName: 'A Co', orderIndex: 0 },
                { ...pendingAnalysis, id: 'm', companyName: 'M Co', orderIndex: 1 },
            ]
            const { container } = render(<PortfolioView scanId="scan-1" initialScan={makeScan(shuffled)} />)
            expect(getCardCompanyNames(container)).toEqual(['A Co', 'M Co', 'Z Co'])
        })

        it('falls back to id sort when orderIndex is null (legacy)', () => {
            const legacy = [
                { ...pendingAnalysis, id: 'z', companyName: 'Z Co', orderIndex: null },
                { ...pendingAnalysis, id: 'a', companyName: 'A Co', orderIndex: null },
            ]
            const { container } = render(<PortfolioView scanId="scan-1" initialScan={makeScan(legacy)} />)
            // Both legacy → sort by id ascending: 'a' before 'z'.
            expect(getCardCompanyNames(container)).toEqual(['A Co', 'Z Co'])
        })

        it('mixes legacy and new entries: numeric orderIndex sorts before null', () => {
            const mixed = [
                { ...pendingAnalysis, id: 'legacy-z', companyName: 'L-Z', orderIndex: null },
                { ...pendingAnalysis, id: 'new-1', companyName: 'N-1', orderIndex: 1 },
                { ...pendingAnalysis, id: 'new-0', companyName: 'N-0', orderIndex: 0 },
                { ...pendingAnalysis, id: 'legacy-a', companyName: 'L-A', orderIndex: null },
            ]
            const { container } = render(<PortfolioView scanId="scan-1" initialScan={makeScan(mixed)} />)
            // Numeric orderIndex first (0, 1), then legacy by id (legacy-a, legacy-z).
            expect(getCardCompanyNames(container)).toEqual(['N-0', 'N-1', 'L-A', 'L-Z'])
        })

        it('done-without-score renders Analyzed (not Pending)', () => {
            // Backend inconsistency: state=done but overallRiskScore is null
            // (e.g., persist step partially failed). The wrapper says done,
            // so the inner content must NOT fall through to Pending.
            const doneNoScore: ScanAnalysis = {
                ...doneAnalysis,
                overallRiskScore: null,
                riskTier: null,
            }
            const { container } = render(
                <PortfolioView scanId="scan-1" initialScan={makeScan([doneNoScore], 'complete')} />
            )
            expect(container.querySelector('.card[data-state="done"]')).toBeInTheDocument()
            expect(screen.queryByText('Pending')).not.toBeInTheDocument()
            // Both card + table show "Analyzed" affordance
            expect(screen.getAllByText('Analyzed').length).toBe(2)
        })
    })

    describe('progress strip + summary stats', () => {
        it('shows progress strip when scan is running', () => {
            const scan = makeScan([doneAnalysis, pendingAnalysis], 'running')
            render(<PortfolioView scanId="scan-1" initialScan={scan} />)
            expect(screen.getByText('1 of 2 done')).toBeInTheDocument()
        })

        it('hides progress strip and shows stats when scan is complete', () => {
            const scan = makeScan([doneAnalysis], 'complete')
            render(<PortfolioView scanId="scan-1" initialScan={scan} />)
            expect(screen.queryByText(/of.*done/)).not.toBeInTheDocument()
            expect(screen.getByText('Avg Risk Score')).toBeInTheDocument()
        })

        it('hides summary stats while scan is running', () => {
            render(<PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />)
            expect(screen.queryByText('Avg Risk Score')).not.toBeInTheDocument()
        })
    })

    describe('polling lifecycle', () => {
        it('polls and updates when pending analyses exist', async () => {
            const resolvedScan = makeScan([doneAnalysis], 'complete')
            ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
                ok: true,
                json: () => Promise.resolve(resolvedScan),
            })

            render(<PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />)

            expect(screen.getAllByText('Pending').length).toBeGreaterThan(0)

            await act(async () => {
                await vi.runAllTimersAsync()
            })

            expect(screen.getAllByText('Acme Corp').length).toBeGreaterThan(0)
        })

        it('does not poll when all analyses are already terminal', () => {
            render(<PortfolioView scanId="scan-1" initialScan={makeScan([doneAnalysis], 'complete')} />)
            vi.advanceTimersByTime(8000)
            expect(global.fetch).not.toHaveBeenCalled()
        })

        it('does not poll when all analyses are failed', () => {
            render(<PortfolioView scanId="scan-1" initialScan={makeScan([failedAnalysis])} />)
            vi.advanceTimersByTime(8000)
            expect(global.fetch).not.toHaveBeenCalled()
        })

        it('continues polling on fetch error without crashing', async () => {
            ;(global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('network error'))

            render(<PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />)

            await act(async () => {
                await vi.advanceTimersByTimeAsync(4000)
            })

            // Still showing pending — not crashed
            expect(screen.getAllByText('Pending').length).toBeGreaterThan(0)
        })
    })
})
