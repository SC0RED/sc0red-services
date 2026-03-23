import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

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

import NewScanPage from '@/app/scan/new/page'

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
        expect(screen.getByPlaceholderText('https://a16z.com')).toBeInTheDocument()
    })

    it('switches to standalone mode when Single Company is clicked', () => {
        render(<NewScanPage />)

        fireEvent.click(screen.getByText('Single Company'))

        expect(screen.getByLabelText('Company Website URL')).toBeInTheDocument()
        expect(screen.getByText('Analyze Company')).toBeInTheDocument()
        expect(screen.getByPlaceholderText('https://stripe.com')).toBeInTheDocument()
    })

    it('switches back to portfolio mode when PE Portfolio Scan is clicked', () => {
        render(<NewScanPage />)

        fireEvent.click(screen.getByText('Single Company'))
        expect(screen.getByLabelText('Company Website URL')).toBeInTheDocument()

        fireEvent.click(screen.getByText('PE Portfolio Scan'))
        expect(screen.getByLabelText('PE Firm Website URL')).toBeInTheDocument()
    })

    it('shows browser validation on submit with empty URL (required field)', () => {
        render(<NewScanPage />)
        const input = screen.getByLabelText('PE Firm Website URL') as HTMLInputElement
        expect(input.required).toBe(true)
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

    it('renders sidebar and session wrapper', () => {
        render(<NewScanPage />)
        expect(screen.getByTestId('dashboard-sidebar')).toBeInTheDocument()
        expect(screen.getByTestId('session-wrapper')).toBeInTheDocument()
    })

    it('shows analyzing phase after form submission', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ scanId: 'scan-1', status: 'running' }),
        })
        global.fetch = fetchMock

        render(<NewScanPage />)

        fireEvent.change(screen.getByLabelText('PE Firm Website URL'), {
            target: { value: 'https://a16z.com' },
        })
        fireEvent.click(screen.getByText('Discover Portfolio & Analyze'))

        await waitFor(() => {
            expect(screen.getByText('Analyzing...')).toBeInTheDocument()
        })
        expect(fetchMock).toHaveBeenCalledWith(
            '/api/scan/start',
            expect.objectContaining({
                method: 'POST',
            })
        )
    })

    it('shows error message when scan start fails', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            ok: false,
            json: () => Promise.resolve({ error: 'Invalid URL provided' }),
        })
        global.fetch = fetchMock

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
        const fetchMock = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ scanId: 'scan-1', status: 'complete', analysisId: 'analysis-1' }),
        })
        global.fetch = fetchMock

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
        let pollCallback: (() => void) | null
        const realSetInterval = globalThis.setInterval.bind(globalThis)

        beforeEach(() => {
            pollCallback = null
            // Intercept setInterval: capture 3000ms poll callbacks, pass others through
            vi.spyOn(global, 'setInterval').mockImplementation((callback: () => void, delay?: number) => {
                if (delay === 3000) {
                    pollCallback = callback
                    return 999 as unknown as ReturnType<typeof setInterval>
                }
                return realSetInterval(callback, delay)
            })
            vi.spyOn(global, 'clearInterval').mockImplementation(() => {})
        })

        afterEach(() => {
            vi.restoreAllMocks()
        })

        async function triggerPoll(): Promise<void> {
            if (pollCallback) {
                await act(async () => {
                    await pollCallback!()
                })
            }
        }

        it('polls for status after scan starts running', async () => {
            const fetchMock = vi.fn()
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ scanId: 's-1', status: 'running' }),
            })
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'running',
                        progress: 30,
                        progressLabel: 'Scraping website...',
                    }),
            })
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({ status: 'running', progress: 60, progressLabel: 'Assessing risks...' }),
            })
            global.fetch = fetchMock

            mockGet.mockReturnValue('standalone')
            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('Company Website URL'), {
                target: { value: 'https://stripe.com' },
            })
            fireEvent.click(screen.getByText('Analyze Company'))

            // Wait for initial POST to resolve and set up polling
            await waitFor(() => {
                expect(pollCallback).not.toBeNull()
            })

            // First poll
            await triggerPoll()

            await waitFor(() => {
                expect(screen.getByText('Scraping website...')).toBeInTheDocument()
            })

            // Second poll
            await triggerPoll()

            await waitFor(() => {
                expect(screen.getByText('Assessing risks...')).toBeInTheDocument()
            })
        })

        it('redirects to analysis when poll returns complete', async () => {
            const fetchMock = vi.fn()
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ scanId: 's-1', status: 'running' }),
            })
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () =>
                    Promise.resolve({
                        status: 'complete',
                        analyses: [{ id: 'a-1', analyzedAt: '2026-03-23T00:00:00Z' }],
                    }),
            })
            global.fetch = fetchMock

            mockGet.mockReturnValue('standalone')
            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('Company Website URL'), {
                target: { value: 'https://stripe.com' },
            })
            fireEvent.click(screen.getByText('Analyze Company'))

            await waitFor(() => {
                expect(pollCallback).not.toBeNull()
            })

            await triggerPoll()

            await waitFor(() => {
                expect(mockPush).toHaveBeenCalledWith('/analysis/a-1')
            })
        })

        it('shows error when scan fails during polling', async () => {
            const fetchMock = vi.fn()
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ scanId: 's-1', status: 'running' }),
            })
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'failed' }),
            })
            global.fetch = fetchMock

            mockGet.mockReturnValue('standalone')
            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('Company Website URL'), {
                target: { value: 'https://stripe.com' },
            })
            fireEvent.click(screen.getByText('Analyze Company'))

            await waitFor(() => {
                expect(pollCallback).not.toBeNull()
            })

            await triggerPoll()

            await waitFor(() => {
                expect(screen.getByText('Analysis failed. Please try again.')).toBeInTheDocument()
            })
            expect(screen.getByLabelText('Company Website URL')).toBeInTheDocument()
        })
    })

    describe('portfolio confirm and polling flow', () => {
        let pollCallback: (() => void) | null
        const realSetInterval = globalThis.setInterval.bind(globalThis)

        beforeEach(() => {
            pollCallback = null
            vi.spyOn(global, 'setInterval').mockImplementation((callback: () => void, delay?: number) => {
                if (delay === 3000) {
                    pollCallback = callback
                    return 999 as unknown as ReturnType<typeof setInterval>
                }
                return realSetInterval(callback, delay)
            })
            vi.spyOn(global, 'clearInterval').mockImplementation(() => {})
        })

        afterEach(() => {
            vi.restoreAllMocks()
        })

        async function triggerPoll(): Promise<void> {
            if (pollCallback) {
                await act(async () => {
                    await pollCallback!()
                })
            }
        }

        it('shows portfolio confirmation after discovery', async () => {
            const fetchMock = vi.fn()
            fetchMock.mockResolvedValueOnce({
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
            global.fetch = fetchMock

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
            const fetchMock = vi.fn()
            fetchMock.mockResolvedValueOnce({
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
            global.fetch = fetchMock

            render(<NewScanPage />)

            fireEvent.change(screen.getByLabelText('PE Firm Website URL'), {
                target: { value: 'https://pe-firm.com' },
            })
            fireEvent.click(screen.getByText('Discover Portfolio & Analyze'))

            await waitFor(() => {
                expect(screen.getByText('Portfolio companies discovered')).toBeInTheDocument()
            })

            // POST /api/scan/s-1/confirm
            fetchMock.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve({ status: 'running' }),
            })
            // GET /api/scan/s-1 — first poll: 1/2 complete
            fetchMock.mockResolvedValueOnce({
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

            // Wait for the confirm fetch to complete and polling to be set up
            await waitFor(() => {
                expect(pollCallback).not.toBeNull()
            })

            await triggerPoll()

            await waitFor(() => {
                expect(screen.getByText(/1\/2 complete/)).toBeInTheDocument()
            })
        })
    })
})
