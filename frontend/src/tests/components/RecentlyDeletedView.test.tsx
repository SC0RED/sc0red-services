import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RecentlyDeletedView from '@/app/(authenticated)/settings/recently-deleted/RecentlyDeletedView'
import type { RecentlyDeletedRecord } from '@/lib/types/api'
import { renderWithProviders } from '@/tests/test-utils'

vi.mock('next/link', () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}))

const analysis: RecentlyDeletedRecord = {
    id: 'c-1',
    type: 'analysis',
    displayName: 'Acme Corp',
    scanId: 'scan-1',
    deletedAt: '2026-04-25T12:00:00Z',
    deletedBy: { id: 'user-1', name: 'Alice' },
    parentTombstoned: false,
}

const orphanedAnalysis: RecentlyDeletedRecord = {
    id: 'c-2',
    type: 'analysis',
    displayName: 'Orphaned Co',
    scanId: 'scan-DEAD',
    deletedAt: '2026-04-24T12:00:00Z',
    deletedBy: { id: 'user-1', name: 'Alice' },
    parentTombstoned: true,
}

const scan: RecentlyDeletedRecord = {
    id: 'scan-2',
    type: 'scan',
    displayName: 'https://otherco.com',
    scanId: null,
    deletedAt: '2026-04-23T12:00:00Z',
    deletedBy: null,
    parentTombstoned: false,
}

describe('RecentlyDeletedView', () => {
    beforeEach(() => {
        global.fetch = vi.fn()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('renders the empty state when no records are passed', () => {
        renderWithProviders(<RecentlyDeletedView initialRecords={[]} />)
        expect(screen.getByText(/Nothing deleted in the last 30 days/i)).toBeInTheDocument()
        expect(screen.getByRole('link', { name: /Back to Analyses/i })).toHaveAttribute('href', '/analyses')
    })

    it('renders rows with displayName, type badge, actor, and a Restore button per row', () => {
        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis, scan]} />)

        // displayName + type
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
        expect(screen.getByText('https://otherco.com')).toBeInTheDocument()
        const badges = screen.getAllByText(/^(Analysis|Portfolio scan)$/)
        expect(badges.map((b) => b.textContent)).toEqual(
            expect.arrayContaining(['Analysis', 'Portfolio scan'])
        )

        // Actor name resolution — analysis has Alice; scan has null actor
        // and renders "Unknown".
        expect(screen.getByText('Alice')).toBeInTheDocument()
        expect(screen.getByText('Unknown')).toBeInTheDocument()

        // Two per-row Restore buttons (one per record).
        expect(screen.getAllByRole('button', { name: /^Restore /i })).toHaveLength(2)
    })

    it('shows the parent-tombstoned pill when parentTombstoned is true', () => {
        renderWithProviders(<RecentlyDeletedView initialRecords={[orphanedAnalysis]} />)
        expect(screen.getByText(/Parent also deleted/)).toBeInTheDocument()
    })

    it('search box filters rows client-side by displayName', () => {
        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis, scan]} />)
        const searchBox = screen.getByLabelText('Filter by name')
        fireEvent.change(searchBox, { target: { value: 'acme' } })
        expect(screen.getByText('Acme Corp')).toBeInTheDocument()
        expect(screen.queryByText('https://otherco.com')).not.toBeInTheDocument()
    })

    it('window-chip click triggers a refetch with the chosen window', async () => {
        const fetched: RecentlyDeletedRecord[] = [analysis]
        ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
            ok: true,
            json: async () => ({ records: fetched }),
        })

        renderWithProviders(<RecentlyDeletedView initialRecords={[]} />)
        // Pick the 7d chip — non-default should fire a refetch.
        fireEvent.click(screen.getByRole('button', { name: '7d' }))

        await waitFor(() =>
            expect(global.fetch).toHaveBeenCalledWith('/api/admin/recently-deleted?window=7d')
        )
    })

    it('selecting rows shows BulkActionsBar with Restore N label', () => {
        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis, scan]} />)
        // Two rows = two checkboxes.
        const rowCheckboxes = screen.getAllByRole('checkbox')
        fireEvent.click(rowCheckboxes[0])
        fireEvent.click(rowCheckboxes[1])
        expect(screen.getByRole('button', { name: /Restore 2 selected records/i })).toBeInTheDocument()
    })

    it('per-row Restore POSTs the single id and shows a success toast on no failures', async () => {
        ;(global.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string, init?: RequestInit) => {
            if (init?.method === 'POST') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({ restored: ['c-1'], failed: [] }),
                })
            }
            // Refetch after restore returns an empty list (the
            // restored row is no longer tombstoned).
            return Promise.resolve({
                ok: true,
                json: async () => ({ records: [] }),
            })
        })

        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis]} />)
        fireEvent.click(screen.getByRole('button', { name: 'Restore Acme Corp' }))

        await waitFor(() => {
            const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls
            const post = calls.find((c) => c[1]?.method === 'POST')
            expect(post).toBeDefined()
            expect(post![0]).toBe('/api/admin/restore')
            expect(JSON.parse(post![1].body as string)).toEqual({ ids: ['c-1'] })
        })

        // Success toast surfaces.
        await waitFor(() => expect(screen.getByText('Restored 1 record')).toBeInTheDocument())
    })

    it('bulk Restore POSTs the array of selected ids', async () => {
        ;(global.fetch as ReturnType<typeof vi.fn>).mockImplementation((_url: string, init?: RequestInit) => {
            if (init?.method === 'POST') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({
                        restored: ['c-1', 'scan-2'],
                        failed: [],
                    }),
                })
            }
            return Promise.resolve({
                ok: true,
                json: async () => ({ records: [] }),
            })
        })

        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis, scan]} />)
        const rowCheckboxes = screen.getAllByRole('checkbox')
        fireEvent.click(rowCheckboxes[0])
        fireEvent.click(rowCheckboxes[1])
        fireEvent.click(screen.getByRole('button', { name: /Restore 2 selected records/i }))

        await waitFor(() => {
            const post = (global.fetch as ReturnType<typeof vi.fn>).mock.calls.find(
                (c) => c[1]?.method === 'POST'
            )
            expect(post).toBeDefined()
            expect(JSON.parse(post![1].body as string)).toEqual({
                ids: ['c-1', 'scan-2'],
            })
        })
        await waitFor(() => expect(screen.getByText('Restored 2 records')).toBeInTheDocument())
    })

    it('partial failure (mixed restored + ttl_expired) shows an error toast with the count breakdown', async () => {
        ;(global.fetch as ReturnType<typeof vi.fn>).mockImplementation((_url: string, init?: RequestInit) => {
            if (init?.method === 'POST') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({
                        restored: ['c-1'],
                        failed: [{ id: 'scan-2', reason: 'ttl_expired' }],
                    }),
                })
            }
            return Promise.resolve({
                ok: true,
                json: async () => ({ records: [scan] }),
            })
        })

        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis, scan]} />)
        const rowCheckboxes = screen.getAllByRole('checkbox')
        fireEvent.click(rowCheckboxes[0])
        fireEvent.click(rowCheckboxes[1])
        fireEvent.click(screen.getByRole('button', { name: /Restore 2 selected records/i }))

        await waitFor(() =>
            expect(screen.getByText(/Restored 1, 1 failed: 1 expired \(TTL\)/i)).toBeInTheDocument()
        )
    })

    it('total failure shows a clean error toast with the failure summary', async () => {
        ;(global.fetch as ReturnType<typeof vi.fn>).mockImplementation((_url: string, init?: RequestInit) => {
            if (init?.method === 'POST') {
                return Promise.resolve({
                    ok: true,
                    json: async () => ({
                        restored: [],
                        failed: [{ id: 'c-1', reason: 'ttl_expired' }],
                    }),
                })
            }
            return Promise.resolve({ ok: true, json: async () => ({ records: [] }) })
        })

        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis]} />)
        fireEvent.click(screen.getByRole('button', { name: 'Restore Acme Corp' }))
        await waitFor(() =>
            expect(screen.getByText(/Restore failed: 1 expired \(TTL\)/i)).toBeInTheDocument()
        )
    })

    it('renders a no-matches row when the search filter excludes every record', () => {
        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis]} />)
        const searchBox = screen.getByLabelText('Filter by name')
        fireEvent.change(searchBox, { target: { value: 'no-such-thing' } })
        expect(screen.getByText(/No matches for "no-such-thing"/)).toBeInTheDocument()
    })

    it('aria-pressed flags the active window chip', () => {
        renderWithProviders(<RecentlyDeletedView initialRecords={[]} />)
        const chip30d = screen.getByRole('button', { name: '30d' })
        const chip7d = screen.getByRole('button', { name: '7d' })
        expect(chip30d.getAttribute('aria-pressed')).toBe('true')
        expect(chip7d.getAttribute('aria-pressed')).toBe('false')
    })

    it('column header for actor is present (smoke check on table structure)', () => {
        // Anchors the "Deleted by" column heading. If a future refactor
        // drops it, this test catches it before users notice missing
        // attribution.
        renderWithProviders(<RecentlyDeletedView initialRecords={[analysis]} />)
        const table = screen.getByRole('table')
        expect(within(table).getByText(/Deleted by/i)).toBeInTheDocument()
    })
})
