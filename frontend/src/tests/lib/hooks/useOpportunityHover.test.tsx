import { act, render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import { OpportunityHoverProvider, useOpportunityHover } from '@/lib/hooks/useOpportunityHover'

/**
 * Tests for the cross-section hover provider. The provider is the
 * coordination layer between three analysis tools (strategy map,
 * EBITDA, value chain) and the OpportunitiesList — see the file's
 * own docblock for the mental model.
 *
 * These tests assert state-management semantics in isolation. The
 * source-/target-side wiring of each consumer (e.g. EBITDA chip
 * mouseEnter triggers ``highlightOpportunities``) is covered by
 * each consumer's own component tests.
 */

interface ProbeProps {
    onContext?: (context: ReturnType<typeof useOpportunityHover>) => void
}

function Probe({ onContext }: ProbeProps) {
    const context = useOpportunityHover()
    if (onContext) onContext(context)
    return (
        <div data-testid="probe">
            <span data-testid="probe-count">{context.hoveredOpportunityIndices.length}</span>
            <span data-testid="probe-indices">{context.hoveredOpportunityIndices.join(',')}</span>
        </div>
    )
}

describe('useOpportunityHover — provider state', () => {
    it('starts with an empty hovered set', () => {
        render(
            <OpportunityHoverProvider>
                <Probe />
            </OpportunityHoverProvider>
        )
        expect(screen.getByTestId('probe-count')).toHaveTextContent('0')
        expect(screen.getByTestId('probe-indices')).toHaveTextContent('')
    })

    it('highlightOpportunities replaces the set', () => {
        let context: ReturnType<typeof useOpportunityHover> | null = null
        render(
            <OpportunityHoverProvider>
                <Probe onContext={(c) => (context = c)} />
            </OpportunityHoverProvider>
        )
        // Source A fires first.
        act(() => {
            context!.highlightOpportunities([0, 3])
        })
        expect(screen.getByTestId('probe-indices')).toHaveTextContent('0,3')

        // Source B fires next — set is REPLACED, not merged. The model is
        // "one source highlighted at a time"; a new dispatch wipes the
        // previous one. Re-render picks up new context.
        act(() => {
            context!.highlightOpportunities([5])
        })
        expect(screen.getByTestId('probe-indices')).toHaveTextContent('5')
    })

    it('clearHighlight resets the set to empty', () => {
        let context: ReturnType<typeof useOpportunityHover> | null = null
        render(
            <OpportunityHoverProvider>
                <Probe onContext={(c) => (context = c)} />
            </OpportunityHoverProvider>
        )
        act(() => {
            context!.highlightOpportunities([1, 2])
        })
        expect(screen.getByTestId('probe-count')).toHaveTextContent('2')
        act(() => {
            context!.clearHighlight()
        })
        expect(screen.getByTestId('probe-count')).toHaveTextContent('0')
    })

    it('clearHighlight on an empty set is a no-op (does not trigger a render)', () => {
        // The reducer short-circuits on already-empty state. We can't
        // directly assert "didn't render" without instrumenting React,
        // but we CAN assert reference equality of the returned array
        // — a useReducer that returned a new ``[]`` would break this.
        let context1: ReturnType<typeof useOpportunityHover> | null = null
        let context2: ReturnType<typeof useOpportunityHover> | null = null
        const { rerender } = render(
            <OpportunityHoverProvider>
                <Probe onContext={(c) => (context1 = c)} />
            </OpportunityHoverProvider>
        )
        act(() => {
            context1!.clearHighlight()
        })
        rerender(
            <OpportunityHoverProvider>
                <Probe onContext={(c) => (context2 = c)} />
            </OpportunityHoverProvider>
        )
        // Same reference both times — no churn.
        expect(context2!.hoveredOpportunityIndices).toBe(context1!.hoveredOpportunityIndices)
    })

    it('deduplicates and sorts indices passed to highlightOpportunities', () => {
        // Sources might pass duplicate indices (a node linked to the
        // same opportunity twice) or unsorted indices. The reducer
        // normalises both so consumers can rely on a stable shape.
        let context: ReturnType<typeof useOpportunityHover> | null = null
        render(
            <OpportunityHoverProvider>
                <Probe onContext={(c) => (context = c)} />
            </OpportunityHoverProvider>
        )
        act(() => {
            context!.highlightOpportunities([3, 1, 1, 0, 3])
        })
        expect(screen.getByTestId('probe-indices')).toHaveTextContent('0,1,3')
    })

    it('returns a no-op context to consumers used OUTSIDE the provider', () => {
        // Components rendered without the provider (isolated tests,
        // stories, error boundaries) should still mount harmlessly.
        // The default context returns empty + no-op functions.
        let context: ReturnType<typeof useOpportunityHover> | null = null
        render(<Probe onContext={(c) => (context = c)} />)
        expect(context!.hoveredOpportunityIndices).toEqual([])
        // Calling no-op functions doesn't throw.
        expect(() => context!.highlightOpportunities([1, 2])).not.toThrow()
        expect(() => context!.clearHighlight()).not.toThrow()
        // Calling them ALSO doesn't change the empty state (no
        // dispatch happens outside the provider).
        expect(screen.getByTestId('probe-count')).toHaveTextContent('0')
    })
})

describe('useOpportunityHover — bi-directional propagation', () => {
    it('a source can highlight indices that targets read', () => {
        // The bi-directional contract: any subtree that subscribes via
        // ``useOpportunityHover`` sees the latest highlighted indices,
        // regardless of which subtree dispatched. Here Source dispatches
        // and Target reads — same context.
        let source: ReturnType<typeof useOpportunityHover> | null = null

        render(
            <OpportunityHoverProvider>
                <Probe onContext={(c) => (source = c)} />
                <Probe />
            </OpportunityHoverProvider>
        )

        act(() => {
            source!.highlightOpportunities([2, 4])
        })

        // Both Probes see the same indices.
        const indices = screen.getAllByTestId('probe-indices')
        expect(indices).toHaveLength(2)
        expect(indices[0]).toHaveTextContent('2,4')
        expect(indices[1]).toHaveTextContent('2,4')
    })
})
