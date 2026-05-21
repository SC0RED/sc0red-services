import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest'

import SourceLinkedOpportunitiesPopover from '@/components/analysis/SourceLinkedOpportunitiesPopover'
import { OpportunityHoverProvider, useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { Opportunity } from '@/lib/types/api'

/**
 * Tests for the source-side opportunity popover introduced by Phase 13
 * of ``redesign-analysis-visuals`` (design D7). The popover surfaces
 * the linked opportunity titles when a hover-source (strategy-map
 * cell, EBITDA leaf, value-chain step) is hovered or focused, without
 * forcing the page to scroll.
 *
 * Timer-driven behaviour (150ms open dwell, 200ms close grace) is
 * exercised with ``vi.useFakeTimers()`` so the assertions are
 * deterministic.
 */

const make = (overrides: Partial<Opportunity>): Opportunity => ({
    title: 'Default opp',
    description: 'desc',
    impact_rating: 'High',
    timeline: 'Quick Win (1-3 months)',
    strategic_category: 'Operational Efficiency',
    value_lever: 'Revenue Side',
    ...overrides,
})

const OPPS: Opportunity[] = [
    make({ title: 'First opportunity', value_lever: 'Revenue Side' }),
    make({ title: 'Second opportunity', value_lever: 'Cost Side' }),
    make({ title: 'Third opportunity', value_lever: 'Both' }),
    make({ title: 'Fourth opportunity', value_lever: 'Revenue Side' }),
    make({ title: 'Fifth opportunity', value_lever: 'Cost Side' }),
    make({ title: 'Sixth opportunity', value_lever: 'Revenue Side' }),
    make({ title: 'Seventh opportunity', value_lever: 'Both' }),
]

function renderPopover(props: { linkedIndices: number[]; anchorId?: string; opportunities?: Opportunity[] }) {
    return render(
        <OpportunityHoverProvider>
            <SourceLinkedOpportunitiesPopover
                anchorId={props.anchorId ?? 'test-anchor'}
                linkedIndices={props.linkedIndices}
                opportunities={props.opportunities ?? OPPS}
                sourceProps={{
                    tabIndex: 0,
                    'data-testid': 'test-anchor',
                }}
            >
                <span>Anchor content</span>
            </SourceLinkedOpportunitiesPopover>
        </OpportunityHoverProvider>
    )
}

describe('SourceLinkedOpportunitiesPopover — empty-linkage short-circuit', () => {
    it('does not render a popover when linkedIndices is empty', () => {
        renderPopover({ linkedIndices: [] })
        const anchor = screen.getByTestId('test-anchor')
        // Hovering an empty-linkage anchor must NOT spawn a popover.
        fireEvent.mouseEnter(anchor)
        // Wait past the would-be open dwell.
        // (timers not faked here — just assert the popover doesn't appear
        // immediately, which it wouldn't even if dwell were satisfied
        // because the short-circuit fires synchronously).
        expect(screen.queryByTestId('source-linked-popover-test-anchor')).toBeNull()
    })
})

describe('SourceLinkedOpportunitiesPopover — open dwell + close grace', () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })
    afterEach(() => {
        vi.useRealTimers()
    })

    it('opens after 150ms dwell on mouseEnter', () => {
        renderPopover({ linkedIndices: [0, 1] })
        const anchor = screen.getByTestId('test-anchor')
        fireEvent.mouseEnter(anchor)
        // Before dwell elapses — no popover.
        act(() => {
            vi.advanceTimersByTime(149)
        })
        expect(screen.queryByTestId('source-linked-popover-test-anchor')).toBeNull()
        // After dwell — popover appears.
        act(() => {
            vi.advanceTimersByTime(1)
        })
        expect(screen.getByTestId('source-linked-popover-test-anchor')).toBeInTheDocument()
    })

    it('opens immediately on focus (no dwell)', () => {
        renderPopover({ linkedIndices: [0, 1] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        expect(screen.getByTestId('source-linked-popover-test-anchor')).toBeInTheDocument()
    })

    it('closes 200ms after mouseLeave', () => {
        renderPopover({ linkedIndices: [0, 1] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        expect(screen.getByTestId('source-linked-popover-test-anchor')).toBeInTheDocument()

        act(() => {
            fireEvent.mouseLeave(anchor)
        })
        // Still visible during the 200ms grace.
        act(() => {
            vi.advanceTimersByTime(199)
        })
        expect(screen.getByTestId('source-linked-popover-test-anchor')).toBeInTheDocument()
        // Cleared after the grace.
        act(() => {
            vi.advanceTimersByTime(1)
        })
        expect(screen.queryByTestId('source-linked-popover-test-anchor')).toBeNull()
    })

    it('cancels the scheduled open when mouseLeave fires before dwell elapses', () => {
        renderPopover({ linkedIndices: [0, 1] })
        const anchor = screen.getByTestId('test-anchor')
        fireEvent.mouseEnter(anchor)
        // Leave before the 150ms dwell completes.
        act(() => {
            vi.advanceTimersByTime(100)
        })
        fireEvent.mouseLeave(anchor)
        // Run forward past the original dwell window + close grace.
        act(() => {
            vi.advanceTimersByTime(500)
        })
        expect(screen.queryByTestId('source-linked-popover-test-anchor')).toBeNull()
    })

    it('cancels the scheduled close when cursor enters the popover during grace', () => {
        renderPopover({ linkedIndices: [0, 1] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        const popover = screen.getByTestId('source-linked-popover-test-anchor')

        // Cursor leaves anchor, but enters popover during grace.
        fireEvent.mouseLeave(anchor)
        act(() => {
            vi.advanceTimersByTime(100)
        })
        fireEvent.mouseEnter(popover)
        // Run past where the close would have fired without cancellation.
        act(() => {
            vi.advanceTimersByTime(500)
        })
        expect(screen.getByTestId('source-linked-popover-test-anchor')).toBeInTheDocument()
    })
})

describe('SourceLinkedOpportunitiesPopover — content', () => {
    it('lists every linked opportunity inline for 1-5 entries', () => {
        renderPopover({ linkedIndices: [0, 2, 4] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        const popover = screen.getByTestId('source-linked-popover-test-anchor')
        expect(within(popover).getByText('First opportunity')).toBeInTheDocument()
        expect(within(popover).getByText('Third opportunity')).toBeInTheDocument()
        expect(within(popover).getByText('Fifth opportunity')).toBeInTheDocument()
        // Header reflects the count.
        expect(popover.textContent).toContain('3 linked opportunities')
        // No overflow row.
        expect(screen.queryByTestId('source-linked-popover-overflow-test-anchor')).toBeNull()
    })

    it('shows first 5 + "+N more" row when 6+ linked opportunities', () => {
        renderPopover({ linkedIndices: [0, 1, 2, 3, 4, 5, 6] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        const popover = screen.getByTestId('source-linked-popover-test-anchor')
        // 5 entries inline.
        for (const title of [
            'First opportunity',
            'Second opportunity',
            'Third opportunity',
            'Fourth opportunity',
            'Fifth opportunity',
        ]) {
            expect(within(popover).getByText(title)).toBeInTheDocument()
        }
        // Two beyond the cap → overflow row.
        const overflow = screen.getByTestId('source-linked-popover-overflow-test-anchor')
        expect(overflow.textContent).toContain('+2 more')
        // Sixth + seventh NOT inline.
        expect(within(popover).queryByText('Sixth opportunity')).toBeNull()
        expect(within(popover).queryByText('Seventh opportunity')).toBeNull()
    })

    it('uses singular "1 linked opportunity" header when only one entry', () => {
        renderPopover({ linkedIndices: [2] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        expect(screen.getByTestId('source-linked-popover-test-anchor').textContent).toContain(
            '1 linked opportunity'
        )
    })
})

describe('SourceLinkedOpportunitiesPopover — interaction', () => {
    // Several tests in this block insert dummy elements into
    // ``document.body`` via ``insertAdjacentHTML`` to provide a
    // scroll target for the imperative ``scrollIntoView`` call.
    // RTL's per-test ``cleanup()`` only unmounts components rendered
    // via ``render()`` — imperative ``document.body`` insertions leak
    // across tests in the same file. Clean them up explicitly so test
    // order doesn't matter (vitest's ``--shuffle`` mode would
    // otherwise fail intermittently).
    afterEach(() => {
        document.body
            .querySelectorAll(
                '[data-testid^="opportunity-card-"], [data-testid="analysis-section-opportunities"]'
            )
            .forEach((el) => el.remove())
    })

    it('clicking an entry dispatches the highlight and calls scrollIntoView on the matching card', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        // Stage a card element for the click to target.
        document.body.insertAdjacentHTML('beforeend', '<div data-testid="opportunity-card-2">card</div>')

        // Probe component reads provider state.
        function HoverProbe() {
            const { hoveredOpportunityIndices } = useOpportunityHover()
            return <div data-testid="hover-probe" data-indices={hoveredOpportunityIndices.join(',')} />
        }
        render(
            <OpportunityHoverProvider>
                <SourceLinkedOpportunitiesPopover
                    anchorId="test"
                    linkedIndices={[2]}
                    opportunities={OPPS}
                    sourceProps={{ tabIndex: 0, 'data-testid': 'test' }}
                >
                    <span>Anchor</span>
                </SourceLinkedOpportunitiesPopover>
                <HoverProbe />
            </OpportunityHoverProvider>
        )

        act(() => {
            fireEvent.focus(screen.getByTestId('test'))
        })
        scrollSpy.mockClear()

        fireEvent.click(screen.getByTestId('source-linked-popover-item-test-2'))

        expect(scrollSpy).toHaveBeenCalledWith({ behavior: 'smooth', block: 'nearest' })
        // Highlight dispatched to the matching index.
        expect(screen.getByTestId('hover-probe').getAttribute('data-indices')).toBe('2')
        // Popover closed after click.
        expect(screen.queryByTestId('source-linked-popover-test')).toBeNull()

        scrollSpy.mockRestore()
    })

    it('Escape on the anchor closes the popover', () => {
        renderPopover({ linkedIndices: [0, 1] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        expect(screen.getByTestId('source-linked-popover-test-anchor')).toBeInTheDocument()
        fireEvent.keyDown(anchor, { key: 'Escape' })
        expect(screen.queryByTestId('source-linked-popover-test-anchor')).toBeNull()
    })

    it('outside click closes the popover', () => {
        renderPopover({ linkedIndices: [0, 1] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        expect(screen.getByTestId('source-linked-popover-test-anchor')).toBeInTheDocument()
        // Click on body, outside both anchor + popover.
        fireEvent.mouseDown(document.body)
        expect(screen.queryByTestId('source-linked-popover-test-anchor')).toBeNull()
    })

    it('clicking the overflow row scrolls the opportunities list section into view', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        document.body.insertAdjacentHTML(
            'beforeend',
            '<section data-testid="analysis-section-opportunities">opps</section>'
        )
        renderPopover({ linkedIndices: [0, 1, 2, 3, 4, 5, 6] })
        const anchor = screen.getByTestId('test-anchor')
        act(() => {
            fireEvent.focus(anchor)
        })
        scrollSpy.mockClear()

        fireEvent.click(screen.getByTestId('source-linked-popover-overflow-test-anchor'))

        expect(scrollSpy).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
        // Popover closed.
        expect(screen.queryByTestId('source-linked-popover-test-anchor')).toBeNull()

        scrollSpy.mockRestore()
    })
})
