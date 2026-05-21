import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

import PortfolioConfirmPhase from '@/components/scan/PortfolioConfirmPhase'

const mockCompanies = [
    { name: 'Acme Corp', url: 'https://acme.com', description: 'A corp', selected: true },
    { name: 'Beta Inc', url: 'https://beta.com', description: 'B corp', selected: true },
    { name: 'Gamma LLC', url: 'https://gamma.com', description: 'G corp', selected: false },
]

describe('PortfolioConfirmPhase', () => {
    const defaultProps = {
        companies: mockCompanies,
        onCompanyToggle: vi.fn(),
        onAddCompany: vi.fn(),
        onConfirm: vi.fn(),
        onReset: vi.fn(),
    }

    it('renders all companies', () => {
        render(<PortfolioConfirmPhase {...defaultProps} />)
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
        expect(screen.getByText('Beta Inc')).toBeInTheDocument()
        expect(screen.getByText('Gamma LLC')).toBeInTheDocument()
    })

    it('renders company URLs', () => {
        render(<PortfolioConfirmPhase {...defaultProps} />)
        expect(screen.getByText('https://acme.com')).toBeInTheDocument()
        expect(screen.getByText('https://beta.com')).toBeInTheDocument()
    })

    it('shows correct selected count', () => {
        render(<PortfolioConfirmPhase {...defaultProps} />)
        expect(screen.getByText('2/3 selected')).toBeInTheDocument()
    })

    it('shows correct count on analyze button', () => {
        render(<PortfolioConfirmPhase {...defaultProps} />)
        expect(screen.getByText('Analyze 2 Companies')).toBeInTheDocument()
    })

    it('renders checkboxes with correct state', () => {
        render(<PortfolioConfirmPhase {...defaultProps} />)
        const checkboxes = screen.getAllByRole('checkbox')
        expect(checkboxes).toHaveLength(3)
        expect(checkboxes[0]).toBeChecked()
        expect(checkboxes[1]).toBeChecked()
        expect(checkboxes[2]).not.toBeChecked()
    })

    it('calls onCompanyToggle when checkbox changes', () => {
        const onCompanyToggle = vi.fn()
        render(<PortfolioConfirmPhase {...defaultProps} onCompanyToggle={onCompanyToggle} />)

        const checkboxes = screen.getAllByRole('checkbox')
        fireEvent.click(checkboxes[2])
        expect(onCompanyToggle).toHaveBeenCalledWith(2, true)
    })

    it('calls onConfirm when analyze button is clicked', () => {
        const onConfirm = vi.fn()
        render(<PortfolioConfirmPhase {...defaultProps} onConfirm={onConfirm} />)

        fireEvent.click(screen.getByText('Analyze 2 Companies'))
        expect(onConfirm).toHaveBeenCalled()
    })

    it('calls onReset when Start Over is clicked', () => {
        const onReset = vi.fn()
        render(<PortfolioConfirmPhase {...defaultProps} onReset={onReset} />)

        fireEvent.click(screen.getByText('Start Over'))
        expect(onReset).toHaveBeenCalled()
    })

    it('shows discovered companies header', () => {
        render(<PortfolioConfirmPhase {...defaultProps} />)
        expect(screen.getByText('Portfolio companies discovered')).toBeInTheDocument()
        expect(screen.getByText(/Found 3 companies/)).toBeInTheDocument()
    })

    describe('manual company addition', () => {
        it('shows Add Company Manually button', () => {
            render(<PortfolioConfirmPhase {...defaultProps} />)
            expect(screen.getByText('+ Add Company Manually')).toBeInTheDocument()
        })

        it('expands form when Add Company Manually is clicked', () => {
            render(<PortfolioConfirmPhase {...defaultProps} />)
            fireEvent.click(screen.getByText('+ Add Company Manually'))

            expect(screen.getByLabelText('Company Name')).toBeInTheDocument()
            expect(screen.getByLabelText('Company URL')).toBeInTheDocument()
            expect(screen.getByText('Add')).toBeInTheDocument()
            expect(screen.getByText('Cancel')).toBeInTheDocument()
        })

        it('collapses form when Cancel is clicked', () => {
            render(<PortfolioConfirmPhase {...defaultProps} />)
            fireEvent.click(screen.getByText('+ Add Company Manually'))
            fireEvent.click(screen.getByText('Cancel'))

            expect(screen.getByText('+ Add Company Manually')).toBeInTheDocument()
            expect(screen.queryByLabelText('Company Name')).not.toBeInTheDocument()
        })

        it('calls onAddCompany with valid inputs', () => {
            const onAddCompany = vi.fn()
            render(<PortfolioConfirmPhase {...defaultProps} onAddCompany={onAddCompany} />)

            fireEvent.click(screen.getByText('+ Add Company Manually'))
            fireEvent.change(screen.getByLabelText('Company Name'), {
                target: { value: 'New Corp' },
            })
            fireEvent.change(screen.getByLabelText('Company URL'), {
                target: { value: 'https://newcorp.com' },
            })
            fireEvent.click(screen.getByText('Add'))

            // ``normalizeUserUrl`` (Diagnostic Tool Feedback #1) parses
            // ``https://newcorp.com`` through the URL constructor, which
            // canonicalises it by appending a trailing slash on the
            // bare-host form. We accept the canonical form here — the
            // backend treats the trailing slash as equivalent.
            expect(onAddCompany).toHaveBeenCalledWith('New Corp', 'https://newcorp.com/')
        })

        it('accepts bare hostnames and auto-prepends https://', () => {
            // Diagnostic Tool Feedback #1: a user typing ``newcorp.com``
            // (no scheme) used to be rejected with the unhelpful
            // ``URL must start with http:// or https://`` error.
            // ``normalizeUserUrl`` now accepts bare hostnames and
            // normalises them to ``https://...`` before handing off.
            const onAddCompany = vi.fn()
            render(<PortfolioConfirmPhase {...defaultProps} onAddCompany={onAddCompany} />)

            fireEvent.click(screen.getByText('+ Add Company Manually'))
            fireEvent.change(screen.getByLabelText('Company Name'), {
                target: { value: 'Bare Co' },
            })
            fireEvent.change(screen.getByLabelText('Company URL'), {
                target: { value: 'bareco.com' },
            })
            fireEvent.click(screen.getByText('Add'))

            expect(onAddCompany).toHaveBeenCalledWith('Bare Co', 'https://bareco.com/')
        })

        it('shows error when name is empty', () => {
            render(<PortfolioConfirmPhase {...defaultProps} />)
            fireEvent.click(screen.getByText('+ Add Company Manually'))
            fireEvent.change(screen.getByLabelText('Company URL'), {
                target: { value: 'https://newcorp.com' },
            })
            fireEvent.click(screen.getByText('Add'))

            expect(screen.getByText('Both name and URL are required.')).toBeInTheDocument()
            expect(defaultProps.onAddCompany).not.toHaveBeenCalled()
        })

        it('shows error when URL is empty', () => {
            render(<PortfolioConfirmPhase {...defaultProps} />)
            fireEvent.click(screen.getByText('+ Add Company Manually'))
            fireEvent.change(screen.getByLabelText('Company Name'), {
                target: { value: 'New Corp' },
            })
            fireEvent.click(screen.getByText('Add'))

            expect(screen.getByText('Both name and URL are required.')).toBeInTheDocument()
        })

        it('shows the friendly URL error for malformed input', () => {
            // ``normalizeUserUrl`` (Diagnostic Tool Feedback #1) replaced
            // the previous "URL must start with http:// or https://"
            // rejection with a single sentence-case error covering all
            // shape failures. ``ftp://`` parses as a valid URL, so the
            // shape check that triggers here is the "no dot in hostname"
            // soft guard — fed a single bare word.
            render(<PortfolioConfirmPhase {...defaultProps} />)
            fireEvent.click(screen.getByText('+ Add Company Manually'))
            fireEvent.change(screen.getByLabelText('Company Name'), {
                target: { value: 'New Corp' },
            })
            fireEvent.change(screen.getByLabelText('Company URL'), {
                target: { value: 'notarealurl' },
            })
            fireEvent.click(screen.getByText('Add'))

            expect(
                screen.getByText(
                    "Enter a website URL — we'll add https:// for you. e.g. stripe.com or www.stripe.com"
                )
            ).toBeInTheDocument()
        })

        it('clears form and collapses after successful add', () => {
            const onAddCompany = vi.fn()
            render(<PortfolioConfirmPhase {...defaultProps} onAddCompany={onAddCompany} />)

            fireEvent.click(screen.getByText('+ Add Company Manually'))
            fireEvent.change(screen.getByLabelText('Company Name'), {
                target: { value: 'New Corp' },
            })
            fireEvent.change(screen.getByLabelText('Company URL'), {
                target: { value: 'https://newcorp.com' },
            })
            fireEvent.click(screen.getByText('Add'))

            // Form should collapse back to button
            expect(screen.getByText('+ Add Company Manually')).toBeInTheDocument()
            expect(screen.queryByLabelText('Company Name')).not.toBeInTheDocument()
        })
    })
})
