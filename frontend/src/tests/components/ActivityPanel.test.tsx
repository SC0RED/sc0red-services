import { fireEvent, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/hooks/useActivityPolling', () => ({
    useActivityPolling: vi.fn(),
}))

import ActivityPanel from '@/components/ActivityPanel'
import { useActivityPolling } from '@/lib/hooks/useActivityPolling'
import type { ActivityEvent } from '@/lib/types/api'
import { renderWithProviders as render } from '@/tests/test-utils'

const mockUseActivityPolling = vi.mocked(useActivityPolling)

const SAMPLE_EVENTS: ActivityEvent[] = [
    {
        id: 'scan_started:s1',
        type: 'scan_started',
        actor: { id: 'u1', name: 'Alice' },
        target: { id: 's1', name: 'acme.com', type: 'scan' },
        timestamp: '2026-04-26T12:00:00Z',
        summary: 'Alice started a portfolio scan',
    },
    {
        id: 'analysis_completed:c1',
        type: 'analysis_completed',
        actor: { id: 'u1', name: 'Alice' },
        target: { id: 'c1', name: 'Acme Corp', type: 'analysis' },
        timestamp: '2026-04-25T12:00:00Z',
        summary: 'Analysis completed for Acme Corp',
    },
    {
        id: 'member_invited:i1',
        type: 'member_invited',
        actor: { id: 'u1', name: 'Alice' },
        target: { id: 'i1', name: 'bob@org.com', type: 'invitation' },
        timestamp: '2026-04-24T12:00:00Z',
        summary: 'Alice invited bob@org.com',
    },
]

const LAST_VIEWED_KEY = 'sc0red-services-activity-last-viewed'

describe('ActivityPanel', () => {
    beforeEach(() => {
        // jsdom's stub doesn't always implement `clear()`. Remove the
        // single key we care about explicitly.
        try {
            window.localStorage.removeItem(LAST_VIEWED_KEY)
        } catch {
            // ignore
        }
        mockUseActivityPolling.mockReturnValue({
            events: SAMPLE_EVENTS,
            loading: false,
            error: null,
        })
    })

    afterEach(() => {
        vi.clearAllMocks()
    })

    it('renders the bell trigger with an accessible label and starts closed', () => {
        const { container } = render(<ActivityPanel initialLastViewed={null} />)
        const trigger = screen.getByRole('button', { name: /activity/i })
        expect(trigger.getAttribute('aria-expanded')).toBe('false')
        // Panel exists in the DOM but is `aria-hidden` while closed —
        // RTL's `hidden: true` matcher doesn't always look up the
        // accessible name on aria-hidden elements, so we fall back to
        // a CSS query for the closed-state shape assertion.
        const dialog = container.querySelector('[role="dialog"]')
        expect(dialog?.getAttribute('data-state')).toBe('closed')
    })

    it('shows an unread badge sized to the count when last-viewed is null', () => {
        render(<ActivityPanel initialLastViewed={null} />)
        // Trigger label includes count.
        expect(screen.getByRole('button', { name: /activity \(3 unread\)/i })).toBeInTheDocument()
    })

    it('hides the badge when there are no newer events than last-viewed', () => {
        // last-viewed is AFTER all sample timestamps → 0 unread.
        render(<ActivityPanel initialLastViewed="2026-05-01T00:00:00Z" />)
        expect(screen.queryByRole('button', { name: /unread/i })).not.toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Activity' })).toBeInTheDocument()
    })

    it('opens on trigger click, marks read, and clears the badge', () => {
        render(<ActivityPanel initialLastViewed={null} />)
        const trigger = screen.getByRole('button', { name: /activity \(3 unread\)/i })
        fireEvent.click(trigger)

        const dialog = screen.getByRole('dialog', { name: /activity feed/i })
        expect(dialog.getAttribute('data-state')).toBe('open')
        // On open, last-viewed updates → unread count drops to 0 →
        // badge disappears → label changes to plain "Activity".
        expect(screen.getByRole('button', { name: /^activity$/i })).toBeInTheDocument()
    })

    it('persists the last-viewed timestamp to localStorage on open', () => {
        render(<ActivityPanel initialLastViewed={null} />)
        const before = window.localStorage.getItem(LAST_VIEWED_KEY)
        expect(before).toBeNull()

        fireEvent.click(screen.getByRole('button', { name: /activity/i }))

        const after = window.localStorage.getItem(LAST_VIEWED_KEY)
        expect(after).toBeTruthy()
        // Stored as ISO 8601 — parseable date.
        expect(Number.isNaN(Date.parse(after as string))).toBe(false)
    })

    it('renders one row per event with the summary text', () => {
        render(<ActivityPanel initialLastViewed={null} />)
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))

        for (const event of SAMPLE_EVENTS) {
            expect(screen.getByText(event.summary)).toBeInTheDocument()
        }
    })

    it('marks events newer than last-viewed as unread before opening', () => {
        // Closed panel: data-unread reflects the initial lastViewed
        // (the events newer than 2026-04-25T12:00:00Z). Only one event
        // (timestamp 2026-04-26) is newer; the other two are not.
        render(<ActivityPanel initialLastViewed="2026-04-25T12:00:00Z" />)
        // Don't open the panel — opening calls markRead which would
        // shift lastViewed to NOW and zero out the unread badge.
        // We assert via the trigger's accessible label which encodes
        // the unread count at render time.
        expect(screen.getByRole('button', { name: /activity \(1 unread\)/i })).toBeInTheDocument()
    })

    it('renders the loading state when no events have arrived yet', () => {
        mockUseActivityPolling.mockReturnValue({ events: [], loading: true, error: null })
        render(<ActivityPanel initialLastViewed={null} />)
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))
        expect(screen.getByText(/loading activity/i)).toBeInTheDocument()
    })

    it('renders the empty state when the feed has no events', () => {
        mockUseActivityPolling.mockReturnValue({ events: [], loading: false, error: null })
        render(<ActivityPanel initialLastViewed={null} />)
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))
        expect(screen.getByText(/No activity yet\. Run a scan or invite a teammate/i)).toBeInTheDocument()
    })

    it('event rows for analysis_completed link to /analysis/{id}', () => {
        render(<ActivityPanel initialLastViewed={null} />)
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))

        const summary = screen.getByText('Analysis completed for Acme Corp')
        const link = summary.closest('a')
        expect(link?.getAttribute('href')).toBe('/analysis/c1')
    })

    it('event rows for scan_started link to /portfolio/{id}', () => {
        render(<ActivityPanel initialLastViewed={null} />)
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))

        const summary = screen.getByText('Alice started a portfolio scan')
        const link = summary.closest('a')
        expect(link?.getAttribute('href')).toBe('/portfolio/s1')
    })

    it('event rows for member_invited link to /team', () => {
        render(<ActivityPanel initialLastViewed={null} />)
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))

        const summary = screen.getByText('Alice invited bob@org.com')
        const link = summary.closest('a')
        expect(link?.getAttribute('href')).toBe('/team')
    })

    it('Escape closes the panel when open', () => {
        render(<ActivityPanel initialLastViewed={null} />)
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))
        const dialog = screen.getByRole('dialog', { name: /activity feed/i })
        expect(dialog.getAttribute('data-state')).toBe('open')

        fireEvent.keyDown(document, { key: 'Escape' })
        expect(dialog.getAttribute('data-state')).toBe('closed')
    })

    it('clicking the close button closes the panel', () => {
        const { container } = render(<ActivityPanel initialLastViewed={null} />)
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))
        fireEvent.click(screen.getByRole('button', { name: /close activity panel/i }))
        const dialog = container.querySelector('[role="dialog"]')
        expect(dialog?.getAttribute('data-state')).toBe('closed')
    })

    it('clicking outside the panel closes it', () => {
        const { container } = render(
            <div>
                <button type="button">Outside</button>
                <ActivityPanel initialLastViewed={null} />
            </div>
        )
        fireEvent.click(screen.getByRole('button', { name: /activity/i }))
        expect(container.querySelector('[role="dialog"]')?.getAttribute('data-state')).toBe('open')

        fireEvent.pointerDown(screen.getByRole('button', { name: 'Outside' }))
        expect(container.querySelector('[role="dialog"]')?.getAttribute('data-state')).toBe('closed')
    })

    it('caps the badge at 99+', () => {
        const manyEvents = Array.from({ length: 150 }, (_, index) => ({
            ...SAMPLE_EVENTS[0],
            id: `event-${index}`,
            timestamp: `2026-04-${1 + (index % 28)}T00:00:00Z`,
        }))
        mockUseActivityPolling.mockReturnValue({
            events: manyEvents,
            loading: false,
            error: null,
        })
        render(<ActivityPanel initialLastViewed={null} />)
        // Trigger label says "150 unread"; the visual badge says "99+".
        expect(screen.getByRole('button', { name: /150 unread/i })).toBeInTheDocument()
        expect(screen.getByText('99+')).toBeInTheDocument()
    })
})
