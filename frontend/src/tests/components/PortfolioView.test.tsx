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

const completedAnalysis = {
    id: 'a-1',
    companyName: 'Acme Corp',
    companyUrl: 'https://acme.com',
    industry: 'SaaS',
    overallRiskScore: 7.5,
    riskTier: 'high',
    error: null,
    analyzedAt: '2026-03-12T10:00:00Z',
}

const pendingAnalysis = {
    id: 'a-2',
    companyName: 'Beta Inc',
    companyUrl: 'https://beta.com',
    industry: '',
    overallRiskScore: null,
    riskTier: null,
    error: null,
    analyzedAt: null,
}

const failedAnalysis = {
    id: 'a-3',
    companyName: 'Gamma Ltd',
    companyUrl: 'https://gamma.com',
    industry: '',
    overallRiskScore: null,
    riskTier: null,
    error: 'Pipeline failed',
    analyzedAt: null,
}

function makeScan(analyses: ScanAnalysis[], status = 'running') {
    return {
        status,
        progress: 50,
        type: 'portfolio',
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

    it('renders completed analysis with risk score and tier badge', () => {
        render(<PortfolioView scanId="scan-1" initialScan={makeScan([completedAnalysis])} />)
        expect(screen.getAllByText('Acme Corp').length).toBeGreaterThan(0)
        expect(screen.getAllByText('7.5').length).toBeGreaterThan(0)
        expect(screen.getAllByText(/high risk/i).length).toBeGreaterThan(0)
    })

    it('renders queued analysis with Queued label (no pipeline progress)', () => {
        render(<PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />)
        expect(screen.getAllByText('Queued').length).toBeGreaterThan(0)
    })

    it('renders analyzing analysis with Analyzing... label (has pipeline progress)', () => {
        const analyzingAnalysis = { ...pendingAnalysis, pipelineProgress: 30 }
        render(<PortfolioView scanId="scan-1" initialScan={makeScan([analyzingAnalysis])} />)
        expect(screen.getAllByText('Analyzing...').length).toBeGreaterThan(0)
    })

    it('renders failed analysis with company name and FAILED badge', () => {
        render(<PortfolioView scanId="scan-1" initialScan={makeScan([failedAnalysis])} />)
        expect(screen.getAllByText('Gamma Ltd').length).toBeGreaterThan(0)
        expect(screen.getByText('FAILED')).toBeInTheDocument()
    })

    it('renders failed analysis without company name as Unknown Company', () => {
        const noNameFailure = { ...failedAnalysis, companyName: '' }
        render(<PortfolioView scanId="scan-1" initialScan={makeScan([noNameFailure])} />)
        expect(screen.getAllByText('Unknown Company').length).toBeGreaterThan(0)
        expect(screen.getByText('FAILED')).toBeInTheDocument()
    })

    it('shows progress strip when scan is running', () => {
        const scan = makeScan([completedAnalysis, pendingAnalysis], 'running')
        render(<PortfolioView scanId="scan-1" initialScan={scan} />)
        expect(screen.getByText('1 of 2 done')).toBeInTheDocument()
    })

    it('hides progress strip and shows stats when scan is complete', () => {
        const scan = makeScan([completedAnalysis], 'complete')
        render(<PortfolioView scanId="scan-1" initialScan={scan} />)
        expect(screen.queryByText(/of.*done/)).not.toBeInTheDocument()
        expect(screen.getByText('Avg Risk Score')).toBeInTheDocument()
    })

    it('hides summary stats while scan is running', () => {
        render(<PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />)
        expect(screen.queryByText('Avg Risk Score')).not.toBeInTheDocument()
    })

    it('does not show updating indicator when all analyses are complete', () => {
        render(<PortfolioView scanId="scan-1" initialScan={makeScan([completedAnalysis], 'complete')} />)
        expect(screen.queryByText(/updating/i)).not.toBeInTheDocument()
    })

    it('polls and updates when pending analyses exist', async () => {
        const resolvedScan = makeScan([completedAnalysis], 'complete')
        ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(resolvedScan),
        })

        render(<PortfolioView scanId="scan-1" initialScan={makeScan([pendingAnalysis])} />)

        expect(screen.getAllByText('Queued').length).toBeGreaterThan(0)

        await act(async () => {
            await vi.runAllTimersAsync()
        })

        expect(screen.getAllByText('Acme Corp').length).toBeGreaterThan(0)
    })

    it('does not poll when all analyses are already resolved', () => {
        render(<PortfolioView scanId="scan-1" initialScan={makeScan([completedAnalysis], 'complete')} />)
        vi.advanceTimersByTime(8000)
        expect(global.fetch).not.toHaveBeenCalled()
    })

    it('does not poll when all analyses have errors', () => {
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
        expect(screen.getAllByText('Queued').length).toBeGreaterThan(0)
    })
})
