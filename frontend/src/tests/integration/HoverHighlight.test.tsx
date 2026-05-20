/**
 * Integration test for the P5 hover provider wiring.
 *
 * Renders ``ValueChainDiagram`` + ``OpportunitiesList`` together inside
 * ``OpportunityHoverProvider`` and asserts the bi-directional highlight
 * contract:
 *
 *   - Hover a value-chain step with linked indices → matching
 *     ``opportunity-card-{originalIndex}`` wrapper gains ``card-pulse``.
 *   - Mouse-leave the step → highlight class clears.
 *   - Hover an opportunity card → step would dispatch to the provider,
 *     and any other consumer reading hovered indices sees the card's
 *     index. (We assert this via a Probe component that reads the
 *     provider state directly.)
 *
 * jsdom doesn't lay out, so ``scrollIntoView`` is mocked and we only
 * assert it was called (not the actual scroll position). That's good
 * enough to lock down the contract.
 */

import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import EbitdaTree from '@/components/EbitdaTree'
import OpportunitiesList from '@/components/OpportunitiesList'
import ValueChainDiagram from '@/components/ValueChainDiagram'
import { OpportunityHoverProvider, useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { EbitdaNode, Opportunity, ValueChainStep } from '@/lib/types/api'

const SAMPLE_OPPS: Opportunity[] = [
    {
        title: 'Deploy AI chatbot',
        description: 'Reduce L1 ticket volume',
        impact_rating: 'High',
        timeline: '3 months',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Revenue Side',
    },
    {
        title: 'Automate billing reconciliation',
        description: 'Cut manual ops effort',
        impact_rating: 'Medium',
        timeline: '6 months',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Cost Side',
    },
]

const STEPS: ValueChainStep[] = [
    {
        id: 'inbound',
        label: 'Inbound Logistics',
        description: 'Receive + warehouse',
        category: 'primary',
        risk_categories: [],
        opportunity_indices: [0],
    },
    {
        id: 'operations',
        label: 'Operations',
        description: 'Core processing',
        category: 'primary',
        risk_categories: [],
        opportunity_indices: [1],
    },
]

beforeEach(() => {
    // jsdom doesn't implement scrollIntoView. Provide a stub so the
    // ``HoverableOpportunityCard`` effect doesn't throw when it fires.
    Element.prototype.scrollIntoView = vi.fn()
})

describe('hover highlight — value chain step → opportunity card', () => {
    it('hovering a step adds card-pulse to the matching opportunity wrapper', () => {
        render(
            <OpportunityHoverProvider>
                <ValueChainDiagram steps={STEPS} opportunities={SAMPLE_OPPS} summary="test" />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )

        // Initially no card carries the pulse class.
        const card0 = screen.getByTestId('opportunity-card-0')
        const card1 = screen.getByTestId('opportunity-card-1')
        expect(card0).not.toHaveClass('card-pulse')
        expect(card1).not.toHaveClass('card-pulse')

        // Hover the Inbound Logistics step — its opportunity_indices is [0].
        const inboundCard = screen.getByTestId('value-chain-step-inbound')
        const inboundInner = inboundCard.querySelector('.card')!
        fireEvent.mouseEnter(inboundInner)

        // Card 0 lights up; card 1 stays unhighlighted.
        expect(card0).toHaveClass('card-pulse')
        expect(card1).not.toHaveClass('card-pulse')
    })

    it('mouse-leave clears the highlight', () => {
        render(
            <OpportunityHoverProvider>
                <ValueChainDiagram steps={STEPS} opportunities={SAMPLE_OPPS} summary="t" />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )

        const inboundInner = screen.getByTestId('value-chain-step-inbound').querySelector('.card')!
        fireEvent.mouseEnter(inboundInner)
        expect(screen.getByTestId('opportunity-card-0')).toHaveClass('card-pulse')

        fireEvent.mouseLeave(inboundInner)
        expect(screen.getByTestId('opportunity-card-0')).not.toHaveClass('card-pulse')
    })

    it('hovering a different step swaps the highlighted card', () => {
        render(
            <OpportunityHoverProvider>
                <ValueChainDiagram steps={STEPS} opportunities={SAMPLE_OPPS} summary="t" />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )

        const inboundInner = screen.getByTestId('value-chain-step-inbound').querySelector('.card')!
        const operationsInner = screen.getByTestId('value-chain-step-operations').querySelector('.card')!

        fireEvent.mouseEnter(inboundInner)
        expect(screen.getByTestId('opportunity-card-0')).toHaveClass('card-pulse')
        expect(screen.getByTestId('opportunity-card-1')).not.toHaveClass('card-pulse')

        // No mouseLeave between — the provider's "replace, not merge"
        // semantics still produce the right result.
        fireEvent.mouseEnter(operationsInner)
        expect(screen.getByTestId('opportunity-card-0')).not.toHaveClass('card-pulse')
        expect(screen.getByTestId('opportunity-card-1')).toHaveClass('card-pulse')
    })

    it('triggers scrollIntoView on the card transitioning into highlight', () => {
        const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
        render(
            <OpportunityHoverProvider>
                <ValueChainDiagram steps={STEPS} opportunities={SAMPLE_OPPS} summary="t" />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )
        scrollSpy.mockClear()

        const inboundInner = screen.getByTestId('value-chain-step-inbound').querySelector('.card')!
        fireEvent.mouseEnter(inboundInner)

        // ``block: 'nearest'`` only scrolls when the card is offscreen
        // (jsdom doesn't lay out so we just assert the call happened
        // with the right options).
        expect(scrollSpy).toHaveBeenCalledWith({
            behavior: 'smooth',
            block: 'nearest',
        })
    })
})

describe('hover highlight — EBITDA leaf chip → opportunity card', () => {
    it('hovering an EBITDA leaf adds card-pulse to the matching opportunity wrapper', () => {
        const tree: EbitdaNode[] = [
            {
                id: 'rev',
                label: 'Revenue',
                type: 'revenue',
                value_range: '$10M',
                parent_id: null,
                description: 'Total revenue',
                linked_opportunity_indices: [],
                children: [
                    {
                        id: 'subs',
                        label: 'Subscriptions',
                        type: 'revenue',
                        value_range: '$8M',
                        parent_id: 'rev',
                        description: 'Sub revenue',
                        linked_opportunity_indices: [1],
                    },
                ],
            },
        ]

        render(
            <OpportunityHoverProvider>
                <EbitdaTree treeData={tree} opportunities={SAMPLE_OPPS} />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )

        const card1 = screen.getByTestId('opportunity-card-1')
        expect(card1).not.toHaveClass('card-pulse')

        // The leaf chip is an <article>; locate it via its data-testid
        // for the dot strip (which is rendered inside) and walk up.
        const dotStrip = screen.getByTestId('ebitda-linked-opportunity-dots')
        const article = dotStrip.closest('article')
        expect(article).not.toBeNull()
        fireEvent.mouseEnter(article!)

        expect(card1).toHaveClass('card-pulse')
        expect(screen.getByTestId('opportunity-card-0')).not.toHaveClass('card-pulse')
    })
})

describe('hover highlight — keyboard focus / blur', () => {
    it('focusing an opportunity card publishes its index, blur clears', () => {
        let observedIndices: number[] = []
        function Probe() {
            const { hoveredOpportunityIndices } = useOpportunityHover()
            observedIndices = hoveredOpportunityIndices
            return null
        }

        render(
            <OpportunityHoverProvider>
                <Probe />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )

        const card0 = screen.getByTestId('opportunity-card-0')
        act(() => {
            fireEvent.focus(card0)
        })
        expect(observedIndices).toEqual([0])

        act(() => {
            // Blur with no relatedTarget — focus left the document or
            // moved to a non-descendant. Highlight clears.
            fireEvent.blur(card0)
        })
        expect(observedIndices).toEqual([])
    })

    it('focus moving from the wrapper INTO the expand button does NOT clear the highlight', () => {
        // Architecture-reviewer P5 finding: a naive ``onBlur={clearHighlight}``
        // would fire when keyboard focus moves from the wrapper to the
        // ``<button>`` inside ``ExpandableCard`` (onBlur bubbles up via
        // focusout). The guard checks ``relatedTarget`` and bails if
        // focus stayed within the wrapper's subtree.
        let observedIndices: number[] = []
        function Probe() {
            const { hoveredOpportunityIndices } = useOpportunityHover()
            observedIndices = hoveredOpportunityIndices
            return null
        }

        render(
            <OpportunityHoverProvider>
                <Probe />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )

        const card0 = screen.getByTestId('opportunity-card-0')
        const expandButton = card0.querySelector('button')
        expect(expandButton).not.toBeNull()

        act(() => {
            fireEvent.focus(card0)
        })
        expect(observedIndices).toEqual([0])

        // Simulate focus moving from the wrapper to the inner button —
        // ``relatedTarget`` is the inner button, which IS contained by
        // the wrapper. Highlight should persist.
        act(() => {
            fireEvent.blur(card0, { relatedTarget: expandButton })
        })
        expect(observedIndices).toEqual([0])
    })
})

describe('hover highlight — opportunity card → provider state', () => {
    it('hovering an opportunity card publishes its originalIndex', () => {
        let observedIndices: number[] = []
        function Probe() {
            const { hoveredOpportunityIndices } = useOpportunityHover()
            observedIndices = hoveredOpportunityIndices
            return null
        }

        render(
            <OpportunityHoverProvider>
                <Probe />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )

        const card1 = screen.getByTestId('opportunity-card-1')
        act(() => {
            fireEvent.mouseEnter(card1)
        })

        // Card 1 is the second opportunity → originalIndex 1.
        expect(observedIndices).toEqual([1])
    })

    it('clears highlighted indices on mouseLeave', () => {
        let observedIndices: number[] = []
        function Probe() {
            const { hoveredOpportunityIndices } = useOpportunityHover()
            observedIndices = hoveredOpportunityIndices
            return null
        }

        render(
            <OpportunityHoverProvider>
                <Probe />
                <OpportunitiesList opportunities={SAMPLE_OPPS} activeLever="All" />
            </OpportunityHoverProvider>
        )

        const card0 = screen.getByTestId('opportunity-card-0')
        act(() => {
            fireEvent.mouseEnter(card0)
        })
        expect(observedIndices).toEqual([0])

        act(() => {
            fireEvent.mouseLeave(card0)
        })
        expect(observedIndices).toEqual([])
    })
})
