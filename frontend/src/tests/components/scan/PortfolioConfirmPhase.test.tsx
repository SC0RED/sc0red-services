import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

import PortfolioConfirmPhase from '@/components/scan/PortfolioConfirmPhase'
import type { DiscoveryVerdict } from '@/lib/types/scan'

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
        onAddCompanies: vi.fn(() => 0),
        onSearchDeeper: vi.fn(),
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

    describe('discovery verdict', () => {
        const subsetVerdict: DiscoveryVerdict = {
            method: 'web_search',
            count: 3,
            completeness: 'web_search_subset',
            availableActions: ['search_deeper', 'render_site', 'upload_list'],
        }

        it('shows the fallback banner when no verdict is present', () => {
            render(<PortfolioConfirmPhase {...defaultProps} />)
            expect(screen.getByText('Portfolio companies discovered')).toBeInTheDocument()
        })

        it('renders the verdict message and action affordances', () => {
            render(<PortfolioConfirmPhase {...defaultProps} verdict={subsetVerdict} />)
            expect(screen.getByText('This list is likely incomplete')).toBeInTheDocument()
            // upload + search-deeper are live; render-the-site is still "soon"
            expect(screen.getByRole('button', { name: /Upload a list/ })).toBeEnabled()
            expect(screen.getByRole('button', { name: /Search deeper/ })).toBeEnabled()
            expect(screen.getByRole('button', { name: /Render the site/ })).toBeDisabled()
        })

        it('calls onSearchDeeper when "Search deeper" is clicked', () => {
            const onSearchDeeper = vi.fn()
            render(
                <PortfolioConfirmPhase
                    {...defaultProps}
                    verdict={subsetVerdict}
                    onSearchDeeper={onSearchDeeper}
                />
            )
            fireEvent.click(screen.getByRole('button', { name: /Search deeper/ }))
            expect(onSearchDeeper).toHaveBeenCalledOnce()
        })

        it('reveals the upload widget when "Upload a list" is clicked', () => {
            render(<PortfolioConfirmPhase {...defaultProps} verdict={subsetVerdict} />)
            expect(screen.queryByLabelText('Company list file')).not.toBeInTheDocument()
            fireEvent.click(screen.getByRole('button', { name: /Upload a list/ }))
            expect(screen.getByLabelText('Company list file')).toBeInTheDocument()
        })

        it('renders the partial-site-list message with escalation', () => {
            render(
                <PortfolioConfirmPhase
                    {...defaultProps}
                    verdict={{
                        method: 'site',
                        count: 4,
                        completeness: 'partial_site_list',
                        availableActions: ['search_deeper', 'render_site', 'upload_list'],
                    }}
                />
            )
            expect(screen.getByText('This may not be the full list')).toBeInTheDocument()
            expect(screen.getByRole('button', { name: /Search deeper/ })).toBeEnabled()
        })

        it('renders the exhausted message and points to upload only', () => {
            render(
                <PortfolioConfirmPhase
                    {...defaultProps}
                    verdict={{
                        method: 'web_search',
                        count: 10,
                        completeness: 'web_search_exhausted',
                        availableActions: ['upload_list'],
                    }}
                />
            )
            expect(screen.getByText('No more found via search')).toBeInTheDocument()
            expect(screen.getByRole('button', { name: /Upload a list/ })).toBeInTheDocument()
            // exhausted → digging more is unproductive, so no Search-deeper button
            expect(screen.queryByRole('button', { name: /Search deeper/ })).not.toBeInTheDocument()
        })

        it('renders a positive message for a full site list', () => {
            render(
                <PortfolioConfirmPhase
                    {...defaultProps}
                    verdict={{
                        method: 'site',
                        count: 3,
                        completeness: 'full_site_list',
                        availableActions: ['upload_list'],
                    }}
                />
            )
            expect(screen.getByText('Portfolio read from the firm’s site')).toBeInTheDocument()
            expect(screen.queryByRole('button', { name: /Search deeper/ })).not.toBeInTheDocument()
        })

        it('shows the site source anchor when present', () => {
            render(
                <PortfolioConfirmPhase
                    {...defaultProps}
                    verdict={{
                        method: 'site',
                        count: 4,
                        completeness: 'partial_site_list',
                        availableActions: ['search_deeper', 'upload_list'],
                        siteSourceUrl: 'https://insightpartners.com/portfolio',
                    }}
                />
            )
            expect(screen.getByText(/Read from insightpartners\.com\/portfolio/)).toBeInTheDocument()
        })
    })

    describe('per-row provenance badges', () => {
        it('flags web-search rows for verification and marks site rows reliable', () => {
            const companies = [
                {
                    name: 'SiteCo',
                    url: 'https://siteco.com',
                    description: '',
                    selected: true,
                    source: 'site' as const,
                },
                {
                    name: 'WebCo',
                    url: 'https://webco.com',
                    description: '',
                    selected: false,
                    source: 'web_search' as const,
                },
            ]
            render(<PortfolioConfirmPhase {...defaultProps} companies={companies} />)
            expect(screen.getByText('via web search — verify')).toBeInTheDocument()
            expect(screen.getByText(/from firm’s site/)).toBeInTheDocument()
        })
    })
})
