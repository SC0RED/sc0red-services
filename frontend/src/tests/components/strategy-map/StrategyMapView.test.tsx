import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, beforeAll } from 'vitest'

import StrategyMapView from '@/components/strategy-map/StrategyMapView'

import { fullStrategyMap } from './_fixtures'

/**
 * `StrategyMapView` tests under the new graphical layout.
 *
 * The React Flow canvas does not expose chip text via the standard
 * jsdom DOM until the canvas measures itself (which it can't in a
 * headless test). What we CAN reliably assert at this level:
 *   - the section's structural elements render (header, canvas
 *     container, core-values strip)
 *   - the three header sections render as <details> disclosures
 *   - default state is closed; clicking a summary opens that section
 *     and closes any other (single-open accordion)
 *
 * Detailed rendering of individual chips (titles, confidence dots,
 * tooltips) is covered by `StrategyMapNode.test.tsx`. The graph data
 * shape (positions, edges, fallback columns) is covered by
 * `layout.test.ts`.
 */

// React Flow uses `ResizeObserver` and `IntersectionObserver` which
// aren't in jsdom. Stub minimally so the component renders without
// throwing during tests.
beforeAll(() => {
    if (typeof globalThis.ResizeObserver === 'undefined') {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ;(globalThis as any).ResizeObserver = class {
            observe() {}
            unobserve() {}
            disconnect() {}
        }
    }
    if (typeof globalThis.DOMRect === 'undefined') {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ;(globalThis as any).DOMRect = class {
            constructor(
                public x = 0,
                public y = 0,
                public width = 0,
                public height = 0
            ) {}
            top = 0
            right = 0
            bottom = 0
            left = 0
            toJSON() {
                return this
            }
        }
    }
})

const summaryFor = (label: RegExp | string) => {
    const match =
        typeof label === 'string'
            ? screen.getByText(label, { selector: 'summary, summary *' })
            : screen.getByText(label)
    const summary = match.closest('summary')
    if (!summary) throw new Error(`No summary found for ${label}`)
    return summary as HTMLElement
}

describe('StrategyMapView — structural composition', () => {
    it('renders the section root and the React Flow canvas container', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByTestId('strategy-map-view')).toBeInTheDocument()
        expect(screen.getByTestId('strategy-map-canvas')).toBeInTheDocument()
    })

    it('renders the strategy-map header with the section title', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText('Strategy Map')).toBeInTheDocument()
    })

    it("does not render a gaps panel (Phase 2 removed What's Missing)", () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        // The whatsMissing / gaps section was removed end-to-end by the
        // ``redesign-strategy-map`` Phase 2 change.
        expect(screen.queryByTestId('strategy-map-whats-missing')).not.toBeInTheDocument()
    })

    it('renders the core-values strip with a ProvenanceMarker for synthesised values', () => {
        // Per `ai-output-trust-markers`, the inline "(inferred)"
        // parenthetical is replaced by a `ProvenanceMarker` component.
        // The visible label is now "Live our values:" alone, plus a
        // separate ProvenanceMarker element with `aria-label="AI-inferred"`.
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText(/Live our values:/)).toBeInTheDocument()
        expect(screen.getByText(/Care for customers/)).toBeInTheDocument()
        // ProvenanceMarker is present (aria-label is the canonical query).
        expect(screen.getAllByLabelText('AI-inferred').length).toBeGreaterThanOrEqual(1)
    })

    it('renders the confidence-dot legend so chip dots have explained meaning', () => {
        // Every objective chip on the canvas renders a small
        // ``ConfidenceIndicator`` (3 dots, partially filled). Without
        // a legend the dots read as decorative; the legend below the
        // canvas documents the HIGH / MEDIUM / LOW scale inline.
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        const legend = screen.getByTestId('strategy-map-confidence-legend')
        expect(legend).toBeInTheDocument()
        expect(legend).toHaveTextContent(/High/)
        expect(legend).toHaveTextContent(/Medium/)
        expect(legend).toHaveTextContent(/Low/)
        // Each row carries a confidence indicator with the canonical
        // aria-label — guarantees the dot rendering is the same one
        // used on the chips. ``aria-label`` is also the only stable
        // selector for the (visually-hidden-to-AT) dot triple.
        expect(legend.querySelector('[aria-label="Confidence: High"]')).not.toBeNull()
        expect(legend.querySelector('[aria-label="Confidence: Medium"]')).not.toBeNull()
        expect(legend.querySelector('[aria-label="Confidence: Low"]')).not.toBeNull()
    })
})

describe('StrategyMapView — header disclosures (single-open accordion)', () => {
    it('renders the vision statement always-visible', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText(/To be the most appetizing convenience retailer/)).toBeInTheDocument()
    })

    it('renders mission, value proposition, and strategic priorities as <details> disclosures, all closed by default', () => {
        const { container } = render(<StrategyMapView strategyMap={fullStrategyMap} />)
        const detailsElements = container.querySelectorAll('details')
        expect(detailsElements.length).toBe(3)
        // Default state is CLOSED — single-open accordion pattern.
        // User clicks a summary to open one section; opening a different
        // section auto-closes the previous one (single-open accordion).
        for (const details of detailsElements) {
            expect(details.hasAttribute('open')).toBe(false)
        }
    })

    it('renders the mission summary label with a ProvenanceMarker (visible when closed)', () => {
        // Per `ai-output-trust-markers`, the inline "(synthesised)"
        // parenthetical in the mission summary label is replaced by a
        // `ProvenanceMarker` component. The visible label is "Mission"
        // alone; the ProvenanceMarker (aria-label="AI-inferred") sits
        // next to it inside the summary element.
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        const summary = summaryFor('Mission')
        expect(summary).toBeInTheDocument()
        // The summary contains the marker — query inside the closest
        // <summary> element. (Note: there's also one for Vision, hence
        // getAllByLabelText returning multiple is fine; we just verify
        // at least one exists.)
        expect(screen.getAllByLabelText('AI-inferred').length).toBeGreaterThanOrEqual(1)
    })

    it('opens the mission section and shows the statement when the summary is clicked', () => {
        const { container } = render(<StrategyMapView strategyMap={fullStrategyMap} />)
        fireEvent.click(summaryFor('Mission'))

        // Exactly one details is open.
        const openDetails = Array.from(container.querySelectorAll('details')).filter((d) =>
            d.hasAttribute('open')
        )
        expect(openDetails).toHaveLength(1)
        // Mission statement is now in the rendered body.
        expect(
            screen.getByText('Provide convenient food, beverages, and fuel to commuters.')
        ).toBeInTheDocument()
    })

    it('opening a different section auto-closes the previously open one (single-open accordion)', () => {
        const { container } = render(<StrategyMapView strategyMap={fullStrategyMap} />)
        fireEvent.click(summaryFor('Mission'))
        fireEvent.click(summaryFor('Value Proposition'))

        const openDetails = Array.from(container.querySelectorAll('details')).filter((d) =>
            d.hasAttribute('open')
        )
        expect(openDetails).toHaveLength(1)
        expect(openDetails[0].textContent).toMatch(/Value Proposition/i)
    })

    it('clicking the same summary again closes the section', () => {
        const { container } = render(<StrategyMapView strategyMap={fullStrategyMap} />)
        const summary = summaryFor('Mission')
        fireEvent.click(summary)
        fireEvent.click(summary)
        const openDetails = Array.from(container.querySelectorAll('details')).filter((d) =>
            d.hasAttribute('open')
        )
        expect(openDetails).toHaveLength(0)
    })

    it('shows the value-proposition chip + rationale when expanded', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        fireEvent.click(summaryFor('Value Proposition'))
        expect(screen.getByText('Customer Intimacy')).toBeInTheDocument()
        expect(screen.getByText(/Public materials emphasise associate friendliness/)).toBeInTheDocument()
    })

    it('lists every strategic priority with its result text when expanded', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        fireEvent.click(summaryFor('Strategic Priorities'))
        expect(screen.getAllByText('Grow Through Foodservice').length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText('Deliver Convenience and Value').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText(/Best-in-class signature food platform/)).toBeInTheDocument()
        expect(
            screen.getByText(/Industry-leading customer perception of speed and value/)
        ).toBeInTheDocument()
    })
})
