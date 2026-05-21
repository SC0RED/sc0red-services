'use client'

import { createContext, useCallback, useContext, useMemo, useReducer, type ReactNode } from 'react'

/**
 * Cross-section hover-highlight provider for the analysis page.
 *
 * The three analysis tools (strategy map, EBITDA tree, value chain)
 * and the ``QuickWinsMatrix`` (P7) all carry index pointers into the
 * shared ``opportunities`` array. When the user hovers any source —
 * an EBITDA leaf chip, a value-chain step card, a strategy-map cell,
 * a matrix dot — we want every matching opportunity card in the
 * ``OpportunitiesList`` below to pulse + scroll into view if needed.
 * The reverse also works: hovering an opportunity card lights up
 * every source node whose linked-indices include the card's index.
 *
 * This provider is the coordination layer. Sources call
 * ``highlightOpportunities([...indices])`` on mouse-enter / focus;
 * targets read ``hoveredOpportunityIndices`` and apply a visual
 * highlight + scroll-into-view. Indices are the ORIGINAL positions
 * in ``analysis.opportunities`` — callers that work with filtered
 * subsets are responsible for resolving filtered → original before
 * dispatching.
 *
 * Provider mounts at the ``AnalysisDetail`` root so every section
 * below can subscribe. Default no-op context lets components used
 * outside the provider (tests, isolated stories) render harmlessly
 * — calling ``highlightOpportunities`` is a no-op in that case.
 *
 * Phase 5 of the ``redesign-analysis-visuals`` change.
 */

export interface OpportunityHoverContextValue {
    /** Original-index set of opportunities currently highlighted. Empty
     *  when nothing is hovered. Consumers use ``Array.includes`` or
     *  ``Set`` membership to test their own card. */
    hoveredOpportunityIndices: number[]
    /** Sources call this on mouse-enter / focus with the indices they
     *  link to. Replaces the previous set entirely — the model is
     *  "one source highlighted at a time", not additive. */
    highlightOpportunities: (indices: number[]) => void
    /** Sources call this on mouse-leave / blur. */
    clearHighlight: () => void
}

const DEFAULT_CONTEXT: OpportunityHoverContextValue = {
    hoveredOpportunityIndices: [],
    highlightOpportunities: () => {},
    clearHighlight: () => {},
}

const OpportunityHoverContext = createContext<OpportunityHoverContextValue>(DEFAULT_CONTEXT)

type Action = { type: 'highlight'; indices: number[] } | { type: 'clear' }

function reducer(state: number[], action: Action): number[] {
    if (action.type === 'highlight') {
        // De-dupe + sort to make ``includes`` checks O(N) consistent
        // across re-renders. The set is small (typically ≤ 5) so the
        // cost is negligible compared to the predictability gain.
        return Array.from(new Set(action.indices)).sort((a, b) => a - b)
    }
    if (state.length === 0) return state
    return []
}

interface OpportunityHoverProviderProps {
    children: ReactNode
}

export function OpportunityHoverProvider({ children }: OpportunityHoverProviderProps) {
    const [hoveredOpportunityIndices, dispatch] = useReducer(reducer, [])

    const highlightOpportunities = useCallback((indices: number[]) => {
        dispatch({ type: 'highlight', indices })
    }, [])

    const clearHighlight = useCallback(() => {
        dispatch({ type: 'clear' })
    }, [])

    const value = useMemo<OpportunityHoverContextValue>(
        () => ({ hoveredOpportunityIndices, highlightOpportunities, clearHighlight }),
        [hoveredOpportunityIndices, highlightOpportunities, clearHighlight]
    )

    return <OpportunityHoverContext.Provider value={value}>{children}</OpportunityHoverContext.Provider>
}

/**
 * Subscribe to the hover-highlight context. Returns the no-op
 * default when called outside an ``OpportunityHoverProvider`` so
 * components stay rendered (e.g. in isolated unit tests that don't
 * mount the provider).
 */
export function useOpportunityHover(): OpportunityHoverContextValue {
    return useContext(OpportunityHoverContext)
}
