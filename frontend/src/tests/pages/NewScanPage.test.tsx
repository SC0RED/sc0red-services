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
})
