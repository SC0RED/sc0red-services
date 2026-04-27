import { screen, fireEvent, within } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
    usePathname: () => '/analyses',
}))

vi.mock('next-auth/react', () => ({
    useSession: () => ({ data: { user: { name: 'Test' } } }),
    signOut: vi.fn(),
}))

import AnalysesTable from '@/components/AnalysesTable'
import type { AnalysisItem } from '@/lib/types/api'

const mockAnalyses: AnalysisItem[] = [
    {
        id: '1',
        companyName: 'Acme Corp',
        companyUrl: 'https://acme.com',
        industry: 'SaaS',
        overallRiskScore: 8.5,
        riskTier: 'critical',
        analyzedAt: '2026-03-20T00:00:00Z',
        scanType: 'portfolio',
        scanId: 'scan-port-1',
    },
    {
        id: '2',
        companyName: 'Beta Inc',
        companyUrl: 'https://beta.com',
        industry: 'Fintech',
        overallRiskScore: 4.2,
        riskTier: 'moderate',
        analyzedAt: '2026-03-22T00:00:00Z',
        scanType: 'standalone',
        scanId: 'scan-single-1',
    },
    {
        id: '3',
        companyName: 'Gamma LLC',
        companyUrl: 'https://gamma.com',
        industry: 'Healthcare',
        overallRiskScore: 6.8,
        riskTier: 'high',
        analyzedAt: '2026-03-18T00:00:00Z',
        scanType: 'portfolio',
        scanId: 'scan-port-2',
    },
]

describe('AnalysesTable', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('renders all analyses', () => {
        render(<AnalysesTable analyses={mockAnalyses} />)
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
        expect(screen.getByText('Beta Inc')).toBeInTheDocument()
        expect(screen.getByText('Gamma LLC')).toBeInTheDocument()
    })

    it('shows result count', () => {
        render(<AnalysesTable analyses={mockAnalyses} />)
        expect(screen.getByText('3 analyses')).toBeInTheDocument()
    })

    it('renders search input', () => {
        render(<AnalysesTable analyses={mockAnalyses} />)
        expect(screen.getByLabelText('Search analyses')).toBeInTheDocument()
    })

    describe('search', () => {
        it('filters by company name', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'Acme' },
            })
            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.queryByText('Beta Inc')).not.toBeInTheDocument()
            expect(screen.getByText('1 of 3')).toBeInTheDocument()
        })

        it('filters by industry', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'fintech' },
            })
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
            expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument()
        })

        it('shows empty state when no matches', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'zzzzz' },
            })
            expect(screen.getByText('No analyses match your filters.')).toBeInTheDocument()
        })
    })

    describe('tier filter', () => {
        function getFilterChip(label: string) {
            // Filter chips have aria-pressed attribute; table badges don't
            const buttons = screen.getAllByText(label)
            const chip = buttons.find((el) => el.closest('[aria-pressed]'))
            if (!chip) throw new Error(`Filter chip "${label}" not found`)
            return chip
        }

        it('filters by risk tier when chip is clicked', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getFilterChip('Critical Risk'))
            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.queryByText('Beta Inc')).not.toBeInTheDocument()
            expect(screen.queryByText('Gamma LLC')).not.toBeInTheDocument()
        })

        it('clears tier filter when same chip clicked again', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getFilterChip('Critical Risk'))
            expect(screen.queryByText('Beta Inc')).not.toBeInTheDocument()

            fireEvent.click(getFilterChip('Critical Risk'))
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
        })
    })

    describe('combined filters', () => {
        function getFilterChip(label: string) {
            const buttons = screen.getAllByText(label)
            const chip = buttons.find((el) => el.closest('[aria-pressed]'))
            if (!chip) throw new Error(`Filter chip "${label}" not found`)
            return chip
        }

        it('search + tier filter combines with AND logic', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'Acme' },
            })
            fireEvent.click(getFilterChip('Critical Risk'))

            // Acme is critical — should still show
            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.getByText('1 of 3')).toBeInTheDocument()
        })

        it('search + tier filter hides non-matching', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.change(screen.getByLabelText('Search analyses'), {
                target: { value: 'Acme' },
            })
            fireEvent.click(getFilterChip('Low Risk'))

            // Acme is critical, not low — should show empty
            expect(screen.getByText('No analyses match your filters.')).toBeInTheDocument()
        })
    })

    describe('type filter', () => {
        function getTypeChip(label: string) {
            const buttons = screen.getAllByText(label)
            const chip = buttons.find((el) => el.closest('[aria-pressed]'))
            if (!chip) throw new Error(`Type chip "${label}" not found`)
            return chip
        }

        it('filters by scan type', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getTypeChip('Standalone'))
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
            expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument()
        })
    })

    describe('sort', () => {
        it('sorts by company name when column header clicked', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(screen.getByLabelText('Sort by Company'))

            const rows = screen.getAllByRole('row')
            // Header + 3 data rows; first data row should be Acme (ascending)
            expect(rows[1]).toHaveTextContent('Acme Corp')
        })

        it('toggles sort direction on second click', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(screen.getByLabelText('Sort by Company'))
            fireEvent.click(screen.getByLabelText('Sort by Company'))

            const rows = screen.getAllByRole('row')
            // Descending: Gamma should be first
            expect(rows[1]).toHaveTextContent('Gamma LLC')
        })

        it('sorts by risk score', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(screen.getByLabelText('Sort by Risk Score'))

            // Default desc for risk score — highest first (8.5 = Acme)
            const rows = screen.getAllByRole('row')
            expect(rows[1]).toHaveTextContent('Acme Corp')
        })
    })

    describe('clear filters', () => {
        function getFilterChip(label: string) {
            const buttons = screen.getAllByText(label)
            const chip = buttons.find((el) => el.closest('[aria-pressed]'))
            if (!chip) throw new Error(`Filter chip "${label}" not found`)
            return chip
        }

        it('shows clear button when filters are active', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            expect(screen.queryByText('Clear all filters')).not.toBeInTheDocument()

            fireEvent.click(getFilterChip('Critical Risk'))
            expect(screen.getByText('Clear all filters')).toBeInTheDocument()
        })

        it('clears all filters when clicked', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getFilterChip('Critical Risk'))

            fireEvent.click(screen.getByText('Clear all filters'))

            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
            expect(screen.getByText('Gamma LLC')).toBeInTheDocument()
        })
    })

    it('shows empty state with CTA when no analyses exist', () => {
        render(<AnalysesTable analyses={[]} />)
        expect(screen.getByText('No analyses yet. Run your first scan to get started.')).toBeInTheDocument()
        expect(screen.getByText('Start a Scan')).toBeInTheDocument()
    })

    describe('bulk actions', () => {
        function getRowCheckbox(companyName: string): HTMLInputElement {
            const row = screen.getByText(companyName).closest('tr')!
            return within(row).getByRole('checkbox') as HTMLInputElement
        }

        it('does not show the bulk-actions bar when no rows are selected', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            expect(screen.queryByRole('region', { name: /bulk actions/i })).not.toBeInTheDocument()
        })

        it('shows the bulk-actions bar with count after selecting a row', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getRowCheckbox('Acme Corp'))
            const bar = screen.getByRole('region', { name: /bulk actions/i })
            expect(within(bar).getByText('1 selected')).toBeInTheDocument()
        })

        it('renders Compare link only when 2 or 3 rows are selected', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)

            // 1 selected → no Compare link
            fireEvent.click(getRowCheckbox('Acme Corp'))
            expect(screen.queryByRole('link', { name: /compare/i })).not.toBeInTheDocument()

            // 2 selected → Compare 2 link with both ids
            fireEvent.click(getRowCheckbox('Beta Inc'))
            const link2 = screen.getByRole('link', { name: /compare 2/i })
            expect(link2.getAttribute('href')).toBe('/analyses/compare?ids=1,2')

            // 3 selected → Compare 3 link
            fireEvent.click(getRowCheckbox('Gamma LLC'))
            expect(screen.getByRole('link', { name: /compare 3/i })).toBeInTheDocument()
        })

        it('lifts the prior 3-cap on selection — selecting a 4th still works (cap removed)', () => {
            // Regression guard against the legacy compare-only cap of 3 sneaking
            // back. Tier 2 §3 lifts the cap; selection is unbounded for delete.
            const four: AnalysisItem[] = [
                ...mockAnalyses,
                {
                    id: '4',
                    companyName: 'Delta Co',
                    companyUrl: 'https://delta.com',
                    industry: 'Logistics',
                    overallRiskScore: 5.0,
                    riskTier: 'low',
                    analyzedAt: '2026-03-15T00:00:00Z',
                    scanType: 'standalone',
                    scanId: 'scan-single-2',
                },
            ]
            render(<AnalysesTable analyses={four} />)
            fireEvent.click(getRowCheckbox('Acme Corp'))
            fireEvent.click(getRowCheckbox('Beta Inc'))
            fireEvent.click(getRowCheckbox('Gamma LLC'))
            fireEvent.click(getRowCheckbox('Delta Co'))

            const bar = screen.getByRole('region', { name: /bulk actions/i })
            expect(within(bar).getByText('4 selected')).toBeInTheDocument()
            // Compare doesn't render for >3 selected.
            expect(screen.queryByRole('link', { name: /compare/i })).not.toBeInTheDocument()
        })

        it('shift-click without a prior anchor falls through to a normal toggle', () => {
            // Self-review minor #5 on PR #196: explicit coverage for the
            // no-anchor branch in `toggleSelectionAt`. Without a prior
            // toggle the shift-click should act like a regular click on
            // that row and set the anchor going forward.
            render(<AnalysesTable analyses={mockAnalyses} />)
            // Shift-click the very first interaction.
            fireEvent.click(getRowCheckbox('Acme Corp'), { shiftKey: true })

            const bar = screen.getByRole('region', { name: /bulk actions/i })
            expect(within(bar).getByText('1 selected')).toBeInTheDocument()
        })

        it('shift-click selects the range between the anchor and the clicked row', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            // Default sort is analyzedAt desc → Beta Inc (newest), Acme Corp,
            // Gamma LLC (oldest). Click Beta first to set the anchor; shift-
            // click Gamma to select all three.
            fireEvent.click(getRowCheckbox('Beta Inc'))
            fireEvent.click(getRowCheckbox('Gamma LLC'), { shiftKey: true })

            const bar = screen.getByRole('region', { name: /bulk actions/i })
            expect(within(bar).getByText('3 selected')).toBeInTheDocument()
        })

        it('header checkbox toggles every visible row, then clears them', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            const headerCheckbox = screen.getByRole('checkbox', { name: /select all analyses/i })

            fireEvent.click(headerCheckbox)
            expect(
                within(screen.getByRole('region', { name: /bulk actions/i })).getByText('3 selected')
            ).toBeInTheDocument()

            fireEvent.click(headerCheckbox)
            expect(screen.queryByRole('region', { name: /bulk actions/i })).not.toBeInTheDocument()
        })

        it('clears selection when the search filter changes', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getRowCheckbox('Acme Corp'))
            expect(screen.getByRole('region', { name: /bulk actions/i })).toBeInTheDocument()

            const search = screen.getByLabelText('Search analyses') as HTMLInputElement
            fireEvent.change(search, { target: { value: 'beta' } })

            expect(screen.queryByRole('region', { name: /bulk actions/i })).not.toBeInTheDocument()
        })

        it('clears selection when the tier filter changes', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getRowCheckbox('Acme Corp'))
            expect(screen.getByRole('region', { name: /bulk actions/i })).toBeInTheDocument()

            // The tier-filter chips are buttons whose text comes from
            // `getRiskTierLabel`. Click whichever one toggles a filter.
            const highChip = screen.getByRole('button', { name: /high/i })
            fireEvent.click(highChip)

            expect(screen.queryByRole('region', { name: /bulk actions/i })).not.toBeInTheDocument()
        })

        it('clicking Delete N triggers the Toast Undo flow and optimistically removes the rows', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getRowCheckbox('Acme Corp'))
            fireEvent.click(getRowCheckbox('Beta Inc'))

            const deleteButton = screen.getByRole('button', {
                name: /delete 2 selected analyses/i,
            })
            fireEvent.click(deleteButton)

            // Rows visually removed; toast appeared with Undo. Spec D4
            // requires the cascade to be explicit ("and their reports")
            // so users aren't surprised by the report data also being
            // deleted.
            expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument()
            expect(screen.queryByText('Beta Inc')).not.toBeInTheDocument()
            expect(screen.getByText('Deleted 2 analyses and their reports')).toBeInTheDocument()
            expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument()

            // Selection cleared post-trigger so the bar disappears.
            expect(screen.queryByRole('region', { name: /bulk actions/i })).not.toBeInTheDocument()
        })

        it('Undo restores the optimistically-removed rows', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getRowCheckbox('Acme Corp'))
            fireEvent.click(getRowCheckbox('Beta Inc'))
            fireEvent.click(screen.getByRole('button', { name: /delete 2 selected analyses/i }))
            expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument()

            fireEvent.click(screen.getByRole('button', { name: /undo/i }))

            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
        })

        it('Clear button resets selection without deleting', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            fireEvent.click(getRowCheckbox('Acme Corp'))
            fireEvent.click(getRowCheckbox('Beta Inc'))
            fireEvent.click(screen.getByRole('button', { name: /clear selection/i }))

            expect(screen.queryByRole('region', { name: /bulk actions/i })).not.toBeInTheDocument()
            // Rows still in the table.
            expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            expect(screen.getByText('Beta Inc')).toBeInTheDocument()
        })

        // ---- Commit-path tests (fake timers + mocked fetch) -----------
        // The toast undo's 5-second window is `setTimeout`-driven; with
        // fake timers we can advance past the window and observe what
        // `onCommit` does. `vi.advanceTimersByTimeAsync` also flushes the
        // microtask queue so the `Promise.all` inside the hook resolves
        // before assertions run.

        describe('commit path (after 5s undo window)', () => {
            const ORIGINAL_FETCH = global.fetch

            afterEach(() => {
                global.fetch = ORIGINAL_FETCH
                vi.useRealTimers()
            })

            // Helper: build an OK Response for the bulk-delete endpoint
            // with explicit deleted/failed lists.
            function bulkOk(deleted: string[], failed: { id: string; reason: string }[] = []): Response {
                return {
                    ok: true,
                    status: 200,
                    json: async () => ({ deleted, failed, deletedScans: [] }),
                } as Response
            }

            it('fires a single bulk POST after the window expires', async () => {
                vi.useFakeTimers()
                const fetchMock = vi.fn().mockResolvedValue(bulkOk(['1', '2']))
                global.fetch = fetchMock as unknown as typeof fetch

                render(<AnalysesTable analyses={mockAnalyses} />)
                fireEvent.click(getRowCheckbox('Acme Corp'))
                fireEvent.click(getRowCheckbox('Beta Inc'))
                fireEvent.click(screen.getByRole('button', { name: /delete 2 selected analyses/i }))

                await vi.advanceTimersByTimeAsync(5001)

                // ONE bulk request, not N parallel single-deletes. The
                // backend handler does a single race-immune cascade pass.
                expect(fetchMock).toHaveBeenCalledTimes(1)
                const [url, init] = fetchMock.mock.calls[0]
                expect(url).toBe('/api/analyses/bulk-delete')
                expect((init as RequestInit).method).toBe('POST')
                expect(JSON.parse((init as RequestInit).body as string)).toEqual({
                    ids: ['1', '2'],
                })
            })

            it('Undo cancels the commit — no bulk POST fires', async () => {
                vi.useFakeTimers()
                const fetchMock = vi.fn().mockResolvedValue(bulkOk(['1']))
                global.fetch = fetchMock as unknown as typeof fetch

                render(<AnalysesTable analyses={mockAnalyses} />)
                fireEvent.click(getRowCheckbox('Acme Corp'))
                fireEvent.click(screen.getByRole('button', { name: /delete 1 selected analyses/i }))

                fireEvent.click(screen.getByRole('button', { name: /undo/i }))
                await vi.advanceTimersByTimeAsync(5001)

                expect(fetchMock).not.toHaveBeenCalled()
                expect(screen.getByText('Acme Corp')).toBeInTheDocument()
            })

            it('partial failure: only the failed rows reappear, error toast surfaces', async () => {
                vi.useFakeTimers()
                // Acme (id 1) fails; Beta (id 2) succeeds.
                const fetchMock = vi.fn().mockResolvedValue(bulkOk(['2'], [{ id: '1', reason: 'not_found' }]))
                global.fetch = fetchMock as unknown as typeof fetch

                render(<AnalysesTable analyses={mockAnalyses} />)
                fireEvent.click(getRowCheckbox('Acme Corp'))
                fireEvent.click(getRowCheckbox('Beta Inc'))
                fireEvent.click(screen.getByRole('button', { name: /delete 2 selected analyses/i }))

                await vi.advanceTimersByTimeAsync(5001)

                // Failed row restored; succeeded row stays gone.
                expect(screen.getByText('Acme Corp')).toBeInTheDocument()
                expect(screen.queryByText('Beta Inc')).not.toBeInTheDocument()
                expect(screen.getByText(/Failed to delete 1 analysis — restored/)).toBeInTheDocument()
            })

            it('full failure (network error): all rows restored, error toast surfaces', async () => {
                vi.useFakeTimers()
                const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
                global.fetch = fetchMock as unknown as typeof fetch

                render(<AnalysesTable analyses={mockAnalyses} />)
                fireEvent.click(getRowCheckbox('Acme Corp'))
                fireEvent.click(getRowCheckbox('Beta Inc'))
                fireEvent.click(screen.getByRole('button', { name: /delete 2 selected analyses/i }))

                await vi.advanceTimersByTimeAsync(5001)

                expect(screen.getByText('Acme Corp')).toBeInTheDocument()
                expect(screen.getByText('Beta Inc')).toBeInTheDocument()
                expect(screen.getByText(/Network error deleting 2 analyses — restored/)).toBeInTheDocument()
            })

            it('full failure (5xx): all rows restored, error toast surfaces', async () => {
                vi.useFakeTimers()
                const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 } as Response)
                global.fetch = fetchMock as unknown as typeof fetch

                render(<AnalysesTable analyses={mockAnalyses} />)
                fireEvent.click(getRowCheckbox('Acme Corp'))
                fireEvent.click(getRowCheckbox('Beta Inc'))
                fireEvent.click(screen.getByRole('button', { name: /delete 2 selected analyses/i }))

                await vi.advanceTimersByTimeAsync(5001)

                expect(screen.getByText('Acme Corp')).toBeInTheDocument()
                expect(screen.getByText('Beta Inc')).toBeInTheDocument()
                expect(screen.getByText(/Network error deleting 2 analyses — restored/)).toBeInTheDocument()
            })

            it('rapid double-click of Delete N fires the bulk POST only once (re-entry guard)', async () => {
                // Regression guard against the architecture-review CRITICAL
                // finding: without a `deleting` flag, two rapid Delete
                // clicks would both fire `onCommit` independently, racing
                // on setRows and producing duplicate restored rows on Undo.
                vi.useFakeTimers()
                const fetchMock = vi.fn().mockResolvedValue(bulkOk(['1', '2']))
                global.fetch = fetchMock as unknown as typeof fetch

                render(<AnalysesTable analyses={mockAnalyses} />)
                fireEvent.click(getRowCheckbox('Acme Corp'))
                fireEvent.click(getRowCheckbox('Beta Inc'))

                const deleteButton = screen.getByRole('button', {
                    name: /delete 2 selected analyses/i,
                })
                fireEvent.click(deleteButton)
                fireEvent.click(deleteButton)

                await vi.advanceTimersByTimeAsync(5001)

                // Exactly one bulk POST, not two.
                expect(fetchMock).toHaveBeenCalledTimes(1)
            })
        })
    })

    describe('scan-type badge navigation', () => {
        // Asserts on the rendered <a href>, not just text — the failure-mode
        // that #182's failed-card regression had was tests checking only text.
        // Use `within(table)` so we don't accidentally match the toolbar's
        // "Portfolio" filter chip.
        function getBadgeInTable(label: 'Portfolio' | 'Standalone'): HTMLElement {
            const table = screen.getByRole('table')
            return within(table).getByText(label)
        }

        it('Portfolio badge wraps in a link to /portfolio/{scanId}', () => {
            render(<AnalysesTable analyses={[mockAnalyses[0]]} />)
            const link = getBadgeInTable('Portfolio').closest('a')
            expect(link).not.toBeNull()
            expect(link).toHaveAttribute('href', '/portfolio/scan-port-1')
        })

        it('Standalone badge is plain text (no link)', () => {
            render(<AnalysesTable analyses={[mockAnalyses[1]]} />)
            expect(getBadgeInTable('Standalone').closest('a')).toBeNull()
        })

        it('Portfolio badge renders without link when scanId is missing (legacy data)', () => {
            // Defensive: a portfolio analysis missing scanId in older data
            // should not crash and should not produce a broken link.
            const legacyPortfolio: AnalysisItem = { ...mockAnalyses[0], scanId: undefined }
            render(<AnalysesTable analyses={[legacyPortfolio]} />)
            expect(getBadgeInTable('Portfolio').closest('a')).toBeNull()
        })

        it('Each portfolio row links to its own scan', () => {
            render(<AnalysesTable analyses={mockAnalyses} />)
            const table = screen.getByRole('table')
            const allBadges = within(table).getAllByText('Portfolio')
            expect(allBadges).toHaveLength(2)
            const hrefs = allBadges.map((badge) => badge.closest('a')?.getAttribute('href'))
            expect(hrefs).toEqual(['/portfolio/scan-port-1', '/portfolio/scan-port-2'])
        })
    })
})
