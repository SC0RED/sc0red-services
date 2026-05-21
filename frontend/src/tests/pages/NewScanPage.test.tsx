import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

const mockPush = vi.fn()
const mockGet = vi.fn()

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush }),
    useSearchParams: () => ({ get: mockGet }),
}))

vi.mock('next-auth/react', () => ({
    SessionProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useSession: () => ({ data: { user: { name: 'Test', email: 'test@test.com' } }, status: 'authenticated' }),
}))

vi.mock('@/components/DashboardSidebar', () => ({
    default: () => <div data-testid="dashboard-sidebar">Sidebar</div>,
}))

vi.mock('@/components/SessionWrapper', () => ({
    default: ({ children }: { children: React.ReactNode }) => (
        <div data-testid="session-wrapper">{children}</div>
    ),
}))

import NewScanPage from '@/app/(authenticated)/scan/new/page'

/**
 * Wraps a fetch mock so that calls to /api/config (used by useScanRealtime)
 * always return an empty AppSync config, making the hook a no-op in tests.
 * All other URLs are forwarded to the inner mock.
 */
function wrapFetchWithConfigStub(innerMock: ReturnType<typeof vi.fn>): ReturnType<typeof vi.fn> {
    return vi.fn((url: string | URL | Request, init?: RequestInit) => {
        if (typeof url === 'string' && url === '/api/config') {
            return Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ appsyncEndpoint: '', appsyncApiKey: '' }),
            })
        }
        return innerMock(url, init)
    })
}

describe('NewScanPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockGet.mockReturnValue(null)
        global.fetch = vi.fn()
    })

    it('renders without crashing', () => {
        render(<NewScanPage />)
        expect(screen.getByText('New AI Risk Scan')).toBeInTheDocument()
    })

    it('renders the mode toggle with Portfolio and Single Company options', () => {
        render(<NewScanPage />)
        expect(screen.getByText('PE Portfolio Scan')).toBeInTheDocument()
        expect(screen.getByText('Single Company')).toBeInTheDocument()
    })

    it('renders the URL input and submit button', () => {
        render(<NewScanPage />)
        expect(screen.getByLabelText('PE Firm Website URL')).toBeInTheDocument()
        expect(screen.getByText('Discover Portfolio & Analyze')).toBeInTheDocument()
    })

    it('defaults to portfolio mode and shows portfolio-specific labels', () => {
        render(<NewScanPage />)
        expect(screen.getByLabelText('PE Firm Website URL')).toBeInTheDocument()
        expect(screen.getByText('Discover Portfolio & Analyze')).toBeInTheDocument()
        // Placeholders dropped the explicit ``https://`` scheme as part
        // of Diagnostic Tool Feedback #1 — the input now accepts bare
        // hostnames and auto-prepends ``https://`` via
        // ``normalizeUserUrl``. Updating the placeholder reinforces that
        // bare-domain input is the expected form.
        expect(screen.getByPlaceholderText('a16z.com')).toBeInTheDocument()
    })

    it('switches to standalone mode when Single Company is clicked', () => {
        render(<NewScanPage />)

        fireEvent.click(screen.getByText('Single Company'))

        expect(screen.getByLabelText('Company Website URL')).toBeInTheDocument()
        expect(screen.getByText('Analyze Company')).toBeInTheDocument()
        expect(screen.getByPlaceholderText('stripe.com')).toBeInTheDocument()
    })

    it('switches back to portfolio mode when PE Portfolio Scan is clicked', () => {
        render(<NewScanPage />)

        fireEvent.click(screen.getByText('Single Company'))
        expect(screen.getByLabelText('Company Website URL')).toBeInTheDocument()

        fireEvent.click(screen.getByText('PE Portfolio Scan'))
        expect(screen.getByLabelText('PE Firm Website URL')).toBeInTheDocument()
    })

    it('surfaces the inline error (not the browser-native popup) on empty URL submit', async () => {
        // Phase 11 of redesign-analysis-visuals removed the native
        // ``required`` attribute so empty-submit flows through
        // ``normalizeUserUrl`` and surfaces in the form's
        // ``.alert-error`` bar — same styling as every other
        // validation failure. Browser-native popups don't match the
        // form's design language.
        render(<NewScanPage />)
        const input = screen.getByLabelText('PE Firm Website URL') as HTMLInputElement
        expect(input.required).toBe(false)
        // The submit handler still validates — clicking with empty
        // input shows the friendly inline error.
        fireEvent.click(screen.getByRole('button', { name: /Discover Portfolio & Analyze/i }))
        expect(
            await screen.findByText(/Enter a website URL — we'll add https:\/\/ for you/)
        ).toBeInTheDocument()
    })

    it('respects type=standalone from search params', () => {
        mockGet.mockReturnValue('standalone')
        render(<NewScanPage />)
        expect(screen.getByLabelText('Company Website URL')).toBeInTheDocument()
        expect(screen.getByText('Analyze Company')).toBeInTheDocument()
    })

    it('respects type=portfolio from search params', () => {
        mockGet.mockReturnValue('portfolio')
        render(<NewScanPage />)
        expect(screen.getByLabelText('PE Firm Website URL')).toBeInTheDocument()
    })

    it('shows analyzing phase after form submission', async () => {
        const innerFetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ scanId: 'scan-1', status: 'running' }),
        })
        global.fetch = wrapFetchWithConfigStub(innerFetch)

        render(<NewScanPage />)

        fireEvent.change(screen.getByLabelText('PE Firm Website URL'), {
            target: { value: 'https://a16z.com' },
        })
        fireEvent.click(screen.getByText('Discover Portfolio & Analyze'))

        await waitFor(() => {
            expect(screen.getByText('Analyzing...')).toBeInTheDocument()
        })
        expect(innerFetch).toHaveBeenCalledWith(
            '/api/scan/start',
            expect.objectContaining({
                method: 'POST',
            })
        )
    })

    it('shows error message when scan start fails', async () => {
        const innerFetch = vi.fn().mockResolvedValue({
            ok: false,
            json: () => Promise.resolve({ error: 'Invalid URL provided' }),
        })
        global.fetch = wrapFetchWithConfigStub(innerFetch)

        render(<NewScanPage />)

        fireEvent.change(screen.getByLabelText('PE Firm Website URL'), {
            target: { value: 'https://bad-url.com' },
        })
        fireEvent.click(screen.getByText('Discover Portfolio & Analyze'))

        await waitFor(() => {
            expect(screen.getByText('Invalid URL provided')).toBeInTheDocument()
        })
    })

    it('shows description text for each mode', () => {
        render(<NewScanPage />)
        expect(
            screen.getByText('Auto-discover and analyze all portfolio companies from a PE firm website')
        ).toBeInTheDocument()
        expect(
            screen.getByText("Deep-dive analysis of one company's AI risk exposure and opportunities")
        ).toBeInTheDocument()
    })

    it('redirects to analysis page on complete standalone scan', async () => {
        const innerFetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ scanId: 'scan-1', status: 'complete', analysisId: 'analysis-1' }),
        })
        global.fetch = wrapFetchWithConfigStub(innerFetch)

        mockGet.mockReturnValue('standalone')
        render(<NewScanPage />)

        fireEvent.change(screen.getByLabelText('Company Website URL'), {
            target: { value: 'https://stripe.com' },
        })
        fireEvent.click(screen.getByText('Analyze Company'))

        await waitFor(() => {
            expect(mockPush).toHaveBeenCalledWith('/analysis/analysis-1')
        })
    })

    describe('standalone scan polling flow', () => {
        it('polls for status after scan starts running', async () => {
            const innerFetch = vi.fn()
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ scanId: 's-1', status: 'running' }),
            })
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'running',
                        progress: 30,
                        progressLabel: 'Scraping website...',
                    }),
            })
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({ status: 'running', progress: 60, progressLabel: 'Assessing risks...' }),
            })
            global.fetch = wrapFetchWithConfigStub(innerFetch)

            mockGet.mockReturnValue('standalone')
            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('Company Website URL'), {
                target: { value: 'https://stripe.com' },
            })
            fireEvent.click(screen.getByText('Analyze Company'))

            // Wait for initial POST to resolve, then advance past first poll
            await waitFor(
                () => {
                    expect(screen.getByText('Scraping website...')).toBeInTheDocument()
                },
                { timeout: 3000 }
            )

            await waitFor(
                () => {
                    expect(screen.getByText('Assessing risks...')).toBeInTheDocument()
                },
                { timeout: 3000 }
            )
        })

        it('redirects to analysis when poll returns complete', async () => {
            const innerFetch = vi.fn()
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ scanId: 's-1', status: 'running' }),
            })
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'complete',
                        analyses: [{ id: 'a-1', analyzedAt: '2026-03-23T00:00:00Z' }],
                    }),
            })
            global.fetch = wrapFetchWithConfigStub(innerFetch)

            mockGet.mockReturnValue('standalone')
            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('Company Website URL'), {
                target: { value: 'https://stripe.com' },
            })
            fireEvent.click(screen.getByText('Analyze Company'))

            await waitFor(
                () => {
                    expect(mockPush).toHaveBeenCalledWith('/analysis/a-1')
                },
                { timeout: 3000 }
            )
        })

        it('shows error when scan fails during polling', async () => {
            const innerFetch = vi.fn()
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ scanId: 's-1', status: 'running' }),
            })
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'failed' }),
            })
            global.fetch = wrapFetchWithConfigStub(innerFetch)

            mockGet.mockReturnValue('standalone')
            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('Company Website URL'), {
                target: { value: 'https://stripe.com' },
            })
            fireEvent.click(screen.getByText('Analyze Company'))

            await waitFor(
                () => {
                    expect(screen.getByText('Analysis failed. Please try again.')).toBeInTheDocument()
                },
                { timeout: 3000 }
            )
            expect(screen.getByLabelText('Company Website URL')).toBeInTheDocument()
        })
    })

    describe('portfolio confirm and polling flow', () => {
        it('shows portfolio confirmation after discovery', async () => {
            const innerFetch = vi.fn()
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        scanId: 's-1',
                        status: 'awaiting_confirmation',
                        portfolioCompanies: [
                            { name: 'Acme Corp', url: 'https://acme.com', description: 'A corp' },
                            { name: 'Beta Inc', url: 'https://beta.com', description: 'B corp' },
                        ],
                    }),
            })
            global.fetch = wrapFetchWithConfigStub(innerFetch)

            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('PE Firm Website URL'), {
                target: { value: 'https://pe-firm.com' },
            })
            fireEvent.click(screen.getByText('Discover Portfolio & Analyze'))

            await waitFor(() => {
                expect(screen.getByText('Portfolio companies discovered')).toBeInTheDocument()
            })
            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
            const checkboxes = screen.getAllByRole('checkbox')
            expect(checkboxes).toHaveLength(2)
            expect(checkboxes[0]).toBeChecked()
            expect(checkboxes[1]).toBeChecked()
        })

        it('polls for portfolio progress after confirm', async () => {
            const innerFetch = vi.fn()
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        scanId: 's-1',
                        status: 'awaiting_confirmation',
                        portfolioCompanies: [
                            { name: 'Acme Corp', url: 'https://acme.com', description: 'A corp' },
                            { name: 'Beta Inc', url: 'https://beta.com', description: 'B corp' },
                        ],
                    }),
            })
            global.fetch = wrapFetchWithConfigStub(innerFetch)

            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('PE Firm Website URL'), {
                target: { value: 'https://pe-firm.com' },
            })
            fireEvent.click(screen.getByText('Discover Portfolio & Analyze'))

            await waitFor(() => {
                expect(screen.getByText('Portfolio companies discovered')).toBeInTheDocument()
            })

            // POST /api/scan/s-1/confirm
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'running' }),
            })
            // GET /api/scan/s-1 — first poll: 1/2 complete
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'running',
                        analyses: [
                            { analyzedAt: '2026-03-23T00:00:00Z', pipelineProgress: 100 },
                            { analyzedAt: null, pipelineProgress: 50, pipelineLabel: 'Assessing risks...' },
                        ],
                    }),
            })

            fireEvent.click(screen.getByText('Analyze 2 Companies'))

            await waitFor(() => {
                expect(screen.getByText('Running Portfolio Analysis...')).toBeInTheDocument()
            })

            // First poll has one analyzedAt → early navigation to portfolio page
            await waitFor(
                () => {
                    expect(mockPush).toHaveBeenCalledWith('/portfolio/s-1')
                },
                { timeout: 3000 }
            )
        })

        it('stays on progress bar when no company has completed yet', async () => {
            const innerFetch = vi.fn()
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        scanId: 's-2',
                        status: 'awaiting_confirmation',
                        portfolioCompanies: [
                            { name: 'Acme Corp', url: 'https://acme.com', description: 'A corp' },
                        ],
                    }),
            })
            global.fetch = wrapFetchWithConfigStub(innerFetch)

            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('PE Firm Website URL'), {
                target: { value: 'https://pe-firm.com' },
            })
            fireEvent.click(screen.getByText('Discover Portfolio & Analyze'))

            await waitFor(() => {
                expect(screen.getByText('Portfolio companies discovered')).toBeInTheDocument()
            })

            // POST /api/scan/s-2/confirm
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'running' }),
            })
            // GET /api/scan/s-2 — poll: 0 complete, all still analyzing
            innerFetch.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'running',
                        analyses: [{ analyzedAt: null, pipelineProgress: 30, pipelineLabel: 'Scraping...' }],
                    }),
            })

            mockPush.mockClear()
            fireEvent.click(screen.getByText('Analyze 1 Companies'))

            await waitFor(() => {
                expect(screen.getByText('Running Portfolio Analysis...')).toBeInTheDocument()
            })

            // Wait for poll to fire
            await waitFor(
                () => {
                    expect(screen.getByText(/Scraping/)).toBeInTheDocument()
                },
                { timeout: 3000 }
            )

            // Should NOT have navigated — no analyzedAt yet
            expect(mockPush).not.toHaveBeenCalledWith(expect.stringContaining('/portfolio/'))
        })
    })
})
