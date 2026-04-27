import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

import FailedAnalysisView from '@/components/analysis/FailedAnalysisView'

vi.mock('@/components/DocumentUpload', () => ({
    default: () => <div data-testid="document-upload">DocumentUpload</div>,
}))
vi.mock('@/components/ui', () => ({
    LoadingSpinner: () => <div data-testid="spinner">Loading...</div>,
}))

function makeProps(overrides: Partial<Parameters<typeof FailedAnalysisView>[0]> = {}) {
    return {
        analysisId: 'a-1',
        companyName: 'Endurance Lift',
        companyUrl: 'https://endurancelift.com',
        error: 'AI provider timeout',
        scanId: 'scan-1',
        scanType: 'portfolio',
        documents: [],
        documentError: null,
        reanalyzing: false,
        reanalysisProgress: 0,
        reanalysisLabel: '',
        onRetry: vi.fn(),
        onDocumentsChange: vi.fn(),
        ...overrides,
    }
}

describe('FailedAnalysisView', () => {
    it('renders company name, URL, and error message', () => {
        render(<FailedAnalysisView {...makeProps()} />)
        expect(screen.getByText('Endurance Lift')).toBeInTheDocument()
        expect(screen.getByText('https://endurancelift.com')).toBeInTheDocument()
        expect(screen.getByText('AI provider timeout')).toBeInTheDocument()
        expect(screen.getByText('Analysis Failed')).toBeInTheDocument()
    })

    it('shows "Unknown Company" when companyName is empty', () => {
        render(<FailedAnalysisView {...makeProps({ companyName: '' })} />)
        expect(screen.getByText('Unknown Company')).toBeInTheDocument()
    })

    it('shows Back to Portfolio link for portfolio scans', () => {
        render(<FailedAnalysisView {...makeProps({ scanType: 'portfolio', scanId: 'scan-1' })} />)
        const link = screen.getByRole('link', { name: /Back to Portfolio/ })
        expect(link).toHaveAttribute('href', '/portfolio/scan-1')
    })

    it('hides Back to Portfolio link for standalone scans even when scanId is set', () => {
        render(<FailedAnalysisView {...makeProps({ scanType: 'single', scanId: 'scan-1' })} />)
        expect(screen.queryByRole('link', { name: /Back to Portfolio/ })).not.toBeInTheDocument()
    })

    it('hides Back to Portfolio link when scanId is absent', () => {
        render(<FailedAnalysisView {...makeProps({ scanId: undefined, scanType: undefined })} />)
        expect(screen.queryByRole('link', { name: /Back to Portfolio/ })).not.toBeInTheDocument()
    })

    it('renders Retry Analysis button and calls onRetry on click', () => {
        const onRetry = vi.fn()
        render(<FailedAnalysisView {...makeProps({ onRetry })} />)
        const button = screen.getByText('Retry Analysis')
        fireEvent.click(button)
        expect(onRetry).toHaveBeenCalledTimes(1)
    })

    it('shows spinner and disables retry button while reanalyzing', () => {
        render(
            <FailedAnalysisView
                {...makeProps({
                    reanalyzing: true,
                    reanalysisLabel: 'Scraping website...',
                    reanalysisProgress: 15,
                })}
            />
        )
        expect(screen.getByTestId('spinner')).toBeInTheDocument()
        expect(screen.getByText(/Scraping website.../)).toBeInTheDocument()
        expect(screen.getByText(/15%/)).toBeInTheDocument()
        expect(screen.queryByText('Retry Analysis')).not.toBeInTheDocument()
    })

    it('renders document upload zone', () => {
        render(<FailedAnalysisView {...makeProps()} />)
        expect(screen.getByTestId('document-upload')).toBeInTheDocument()
    })

    it('shows document error when present', () => {
        render(<FailedAnalysisView {...makeProps({ documentError: 'Upload failed' })} />)
        expect(screen.getByText('Upload failed')).toBeInTheDocument()
    })
})
