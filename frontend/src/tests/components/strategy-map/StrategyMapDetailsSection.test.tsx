import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import StrategyMapDetailsSection from '@/components/strategy-map/StrategyMapDetailsSection'
import type { StrategicPriority, ValuePropositionClassification } from '@/lib/types/api'

/**
 * Tests for the relocated Value Proposition + Strategic Priorities
 * section introduced by Phase 12 of ``redesign-analysis-visuals``.
 * The section used to live inside the strategy-map header; Diagnostic
 * Tool Feedback #4 asked for the header to carry only Mission +
 * Vision, so VP + Strategic Priorities moved into this collapsed
 * ``<ExpandableCard>`` below the table.
 */

const FULL_VP: ValuePropositionClassification = {
    primary: 'customer_intimacy',
    secondary: null,
    rationale: 'Public materials emphasise associate friendliness and brand experience.',
    exemplar_company: 'Wawa',
}

const PRIORITIES: StrategicPriority[] = [
    {
        name: 'Grow Through Foodservice',
        result: 'Best-in-class signature food platform driving same-store growth.',
    },
    {
        name: 'Deliver Convenience and Value',
        result: 'Industry-leading customer perception of speed and value.',
    },
]

describe('StrategyMapDetailsSection — trigger label', () => {
    it('renders "Value Proposition & Strategic Priorities · N" when both are present', () => {
        render(<StrategyMapDetailsSection valueProposition={FULL_VP} strategicPriorities={PRIORITIES} />)
        expect(screen.getByTestId('strategy-map-details-trigger')).toHaveTextContent(
            'Value Proposition & Strategic Priorities · 2'
        )
    })

    it('renders "Value Proposition" alone when only VP is present', () => {
        render(<StrategyMapDetailsSection valueProposition={FULL_VP} strategicPriorities={[]} />)
        const trigger = screen.getByTestId('strategy-map-details-trigger')
        expect(trigger).toHaveTextContent('Value Proposition')
        expect(trigger).not.toHaveTextContent('Strategic Priorities')
        expect(trigger).not.toHaveTextContent('·')
    })

    it('renders "Strategic Priorities · N" when only priorities are present', () => {
        const emptyVP = { ...FULL_VP, primary: '', secondary: null, rationale: '' }
        render(
            <StrategyMapDetailsSection
                valueProposition={emptyVP as unknown as ValuePropositionClassification}
                strategicPriorities={PRIORITIES}
            />
        )
        const trigger = screen.getByTestId('strategy-map-details-trigger')
        expect(trigger).toHaveTextContent('Strategic Priorities · 2')
        expect(trigger).not.toHaveTextContent('Value Proposition')
    })
})

describe('StrategyMapDetailsSection — default-closed', () => {
    it('renders the trigger label but hides the body by default', () => {
        render(<StrategyMapDetailsSection valueProposition={FULL_VP} strategicPriorities={PRIORITIES} />)
        // Trigger visible.
        expect(screen.getByTestId('strategy-map-details-trigger')).toBeInTheDocument()
        // Body present in the DOM but hidden via the ExpandableCard's
        // ``hidden`` attribute (which jsdom mirrors with the HTML
        // ``hidden`` property — body retains its testid for queries).
        const body = screen.getByTestId('strategy-map-details-body')
        // ExpandableCard wraps the body with the ``hidden`` attribute
        // when closed; assert the wrapping element carries it.
        expect(body.closest('[hidden]')).not.toBeNull()
    })

    it('clicking the trigger reveals the body', () => {
        render(<StrategyMapDetailsSection valueProposition={FULL_VP} strategicPriorities={PRIORITIES} />)
        const trigger = screen.getByRole('button', { name: /Value Proposition & Strategic Priorities/ })
        fireEvent.click(trigger)
        const body = screen.getByTestId('strategy-map-details-body')
        expect(body.closest('[hidden]')).toBeNull()
    })
})

describe('StrategyMapDetailsSection — content', () => {
    it('expanded body shows VP classification + rationale + every strategic priority', () => {
        render(<StrategyMapDetailsSection valueProposition={FULL_VP} strategicPriorities={PRIORITIES} />)
        fireEvent.click(screen.getByRole('button', { name: /Value Proposition & Strategic Priorities/ }))

        // VP block visible
        expect(screen.getByTestId('strategy-map-value-proposition')).toBeInTheDocument()
        expect(screen.getByText('Customer Intimacy')).toBeInTheDocument()
        expect(screen.getByText(/Public materials emphasise associate friendliness/)).toBeInTheDocument()

        // Priorities block — list of two
        expect(screen.getByTestId('strategy-map-strategic-priorities')).toBeInTheDocument()
        expect(screen.getByText('Grow Through Foodservice')).toBeInTheDocument()
        expect(screen.getByText('Deliver Convenience and Value')).toBeInTheDocument()
        expect(screen.getByText(/Best-in-class signature food platform/)).toBeInTheDocument()
        expect(
            screen.getByText(/Industry-leading customer perception of speed and value/)
        ).toBeInTheDocument()
    })

    it('only the VP block renders when no priorities are present', () => {
        render(<StrategyMapDetailsSection valueProposition={FULL_VP} strategicPriorities={[]} />)
        fireEvent.click(screen.getByRole('button', { name: /Value Proposition/ }))

        expect(screen.getByTestId('strategy-map-value-proposition')).toBeInTheDocument()
        expect(screen.queryByTestId('strategy-map-strategic-priorities')).toBeNull()
    })

    it('only the priorities block renders when VP is absent', () => {
        const emptyVP = { ...FULL_VP, primary: '', rationale: '' }
        render(
            <StrategyMapDetailsSection
                valueProposition={emptyVP as unknown as ValuePropositionClassification}
                strategicPriorities={PRIORITIES}
            />
        )
        fireEvent.click(screen.getByRole('button', { name: /Strategic Priorities/ }))

        expect(screen.queryByTestId('strategy-map-value-proposition')).toBeNull()
        expect(screen.getByTestId('strategy-map-strategic-priorities')).toBeInTheDocument()
    })
})

// Note: the "absent-both" case is gated at the call site in
// ``AnalysisDetail.tsx`` (``hasStrategyDetails`` predicate). The
// component itself trusts its props and renders unconditionally —
// the defensive in-component null-return was removed per CLAUDE.md
// fail-fast. Call-site gating is exercised by the section-order
// regression test in ``tests/pages/AnalysisDetail.test.tsx``.
