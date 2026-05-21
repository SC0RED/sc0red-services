import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

import ScanInputPhase from '@/components/scan/ScanInputPhase'

describe('ScanInputPhase', () => {
    const defaultProps = {
        mode: 'portfolio' as const,
        url: '',
        error: '',
        onModeChange: vi.fn(),
        onUrlChange: vi.fn(),
        onSubmit: vi.fn(),
    }

    it('renders mode toggle buttons', () => {
        render(<ScanInputPhase {...defaultProps} />)
        expect(screen.getByText('PE Portfolio Scan')).toBeInTheDocument()
        expect(screen.getByText('Single Company')).toBeInTheDocument()
    })

    it('shows portfolio-specific labels in portfolio mode', () => {
        render(<ScanInputPhase {...defaultProps} />)
        expect(screen.getByLabelText('PE Firm Website URL')).toBeInTheDocument()
        expect(screen.getByText('Discover Portfolio & Analyze')).toBeInTheDocument()
        // Placeholder dropped the explicit scheme per Diagnostic Tool
        // Feedback #1 — the input accepts bare hostnames and auto-
        // prepends ``https://`` via ``normalizeUserUrl`` in the parent.
        expect(screen.getByPlaceholderText('a16z.com')).toBeInTheDocument()
    })

    it('shows standalone-specific labels in standalone mode', () => {
        render(<ScanInputPhase {...defaultProps} mode="standalone" />)
        expect(screen.getByLabelText('Company Website URL')).toBeInTheDocument()
        expect(screen.getByText('Analyze Company')).toBeInTheDocument()
        expect(screen.getByPlaceholderText('stripe.com')).toBeInTheDocument()
    })

    it('calls onModeChange when mode button is clicked', () => {
        const onModeChange = vi.fn()
        render(<ScanInputPhase {...defaultProps} onModeChange={onModeChange} />)

        fireEvent.click(screen.getByText('Single Company'))
        expect(onModeChange).toHaveBeenCalledWith('standalone')
    })

    it('calls onUrlChange when URL input changes', () => {
        const onUrlChange = vi.fn()
        render(<ScanInputPhase {...defaultProps} onUrlChange={onUrlChange} />)

        fireEvent.change(screen.getByLabelText('PE Firm Website URL'), {
            target: { value: 'https://example.com' },
        })
        expect(onUrlChange).toHaveBeenCalledWith('https://example.com')
    })

    it('calls onSubmit when form is submitted', () => {
        const onSubmit = vi.fn((e) => e.preventDefault())
        render(<ScanInputPhase {...defaultProps} url="https://example.com" onSubmit={onSubmit} />)

        fireEvent.submit(screen.getByText('Discover Portfolio & Analyze').closest('form')!)
        expect(onSubmit).toHaveBeenCalled()
    })

    it('displays error when error prop is set', () => {
        render(<ScanInputPhase {...defaultProps} error="Something went wrong" />)
        expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    })

    it('does not display error div when error is empty', () => {
        const { container } = render(<ScanInputPhase {...defaultProps} />)
        const errorDiv = container.querySelector('[style*="risk-critical"]')
        expect(errorDiv).toBeNull()
    })

    it('omits the native required attribute on the URL input', () => {
        // Phase 11 of redesign-analysis-visuals removed the native
        // ``required`` so empty-submit surfaces the same inline
        // ``.alert-error`` bar as every other validation failure —
        // not the browser-native popup whose styling doesn't match
        // the form. ``normalizeUserUrl`` in the parent's submit
        // handler catches the empty case.
        render(<ScanInputPhase {...defaultProps} />)
        const input = screen.getByLabelText('PE Firm Website URL') as HTMLInputElement
        expect(input.required).toBe(false)
    })

    it('renders description text for each mode', () => {
        render(<ScanInputPhase {...defaultProps} />)
        expect(
            screen.getByText('Auto-discover and analyze all portfolio companies from a PE firm website')
        ).toBeInTheDocument()
        expect(
            screen.getByText("Deep-dive analysis of one company's AI risk exposure and opportunities")
        ).toBeInTheDocument()
    })
})
