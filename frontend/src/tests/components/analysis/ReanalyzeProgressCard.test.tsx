import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import ReanalyzeProgressCard from '@/components/analysis/ReanalyzeProgressCard'

/**
 * Coverage focus: the card is purely presentational, so the tests
 * pin the contracts that downstream consumers depend on:
 *   - The card is reachable by `data-testid="reanalyze-progress"` (so
 *     order-tests on the page can confirm it never renders as a
 *     top-level sibling).
 *   - `id` prop is honoured on the rendered element so consumers can
 *     wire `aria-describedby` from a trigger button.
 *   - `label` falls back to "Starting pipeline..." when undefined or
 *     empty — a pre-realtime-first-message placeholder.
 *   - `progress` is treated as 0 when undefined, both in the bar's
 *     width and in the percent readout.
 *   - `role="status"` + `aria-live="polite"` are present so screen
 *     readers announce updates without interrupting the user.
 */

describe('ReanalyzeProgressCard', () => {
    it('renders the testid so page-level order tests can find it', () => {
        render(<ReanalyzeProgressCard />)
        expect(screen.getByTestId('reanalyze-progress')).toBeInTheDocument()
    })

    it('honours the `id` prop on the rendered element', () => {
        render(<ReanalyzeProgressCard id="reanalyze-progress" />)
        const card = screen.getByTestId('reanalyze-progress')
        expect(card.id).toBe('reanalyze-progress')
    })

    it('does not set an id when none is provided', () => {
        render(<ReanalyzeProgressCard />)
        const card = screen.getByTestId('reanalyze-progress')
        expect(card.id).toBe('')
    })

    it('renders the label verbatim when provided', () => {
        render(<ReanalyzeProgressCard label="Step 3 of 6" />)
        expect(screen.getByText('Step 3 of 6')).toBeInTheDocument()
    })

    it('falls back to "Starting pipeline..." when label is undefined', () => {
        render(<ReanalyzeProgressCard />)
        expect(screen.getByText('Starting pipeline...')).toBeInTheDocument()
    })

    it('falls back to "Starting pipeline..." when label is an empty string', () => {
        render(<ReanalyzeProgressCard label="" />)
        expect(screen.getByText('Starting pipeline...')).toBeInTheDocument()
    })

    it('renders the percent readout from progress', () => {
        render(<ReanalyzeProgressCard progress={42} />)
        expect(screen.getByText('42% complete')).toBeInTheDocument()
    })

    it('treats undefined progress as 0', () => {
        render(<ReanalyzeProgressCard />)
        expect(screen.getByText('0% complete')).toBeInTheDocument()
    })

    it('exposes role="status" with aria-live="polite" for screen-reader announcements', () => {
        render(<ReanalyzeProgressCard />)
        const card = screen.getByTestId('reanalyze-progress')
        expect(card.getAttribute('role')).toBe('status')
        expect(card.getAttribute('aria-live')).toBe('polite')
    })

    it('paints the progress-fill bar at the matching width percentage', () => {
        const { container } = render(<ReanalyzeProgressCard progress={73} />)
        const fill = container.querySelector<HTMLElement>('.progress-fill')
        expect(fill).not.toBeNull()
        expect(fill?.style.width).toBe('73%')
    })
})
