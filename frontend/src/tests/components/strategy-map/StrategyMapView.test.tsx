import { render, screen } from '@testing-library/react'
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
 *     container, core-values strip, gaps panel)
 *   - vision/value-prop chip text appears in the header
 *   - mission disclosure renders closed by default
 *   - the strategic-priority legend lists every priority
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

    it('renders the gaps panel below the canvas', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByTestId('strategy-map-whats-missing')).toBeInTheDocument()
    })

    it('renders the core-values strip with the inferred marker for synthesised values', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText(/Live our values \(inferred\):/)).toBeInTheDocument()
        expect(screen.getByText(/Care for customers/)).toBeInTheDocument()
    })
})

describe('StrategyMapView — header content', () => {
    it('renders the vision statement', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText(/To be the most appetizing convenience retailer/)).toBeInTheDocument()
    })

    it('renders the value-proposition chip', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        // The chip uses formatValueProposition; for primary='customer_intimacy'
        // (no secondary) the result is 'Customer Intimacy'.
        expect(screen.getByText('Customer Intimacy')).toBeInTheDocument()
    })

    it('renders mission, value proposition, and strategic priorities as <details> disclosures', () => {
        const { container } = render(<StrategyMapView strategyMap={fullStrategyMap} />)
        // Three sections in the header band — same disclosure pattern.
        const detailsElements = container.querySelectorAll('details')
        expect(detailsElements.length).toBe(3)
        // Default state is OPEN so the user sees the company positioning
        // on first load. They can collapse any section deliberately.
        for (const details of detailsElements) {
            expect(details.hasAttribute('open')).toBe(true)
        }
    })

    it('renders the mission summary label with synthesised marker', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText(/Mission \(synthesised\)/i)).toBeInTheDocument()
    })

    it('shows the mission statement inside the open disclosure body', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        // Default-open means the statement is visible without interaction.
        expect(
            screen.getByText('Provide convenient food, beverages, and fuel to commuters.')
        ).toBeInTheDocument()
    })

    it('renders the value proposition rationale inside the disclosure body', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        // Rationale moved out of a hover tooltip into the always-visible
        // (when open) disclosure body.
        expect(screen.getByText(/Public materials emphasise associate friendliness/)).toBeInTheDocument()
    })

    it('lists every strategic priority with its result text inside the disclosure body', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        // Priority names appear as highlighted sub-headers; result text
        // appears underneath each one (no longer hidden behind hover).
        expect(screen.getAllByText('Grow Through Foodservice').length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText('Deliver Convenience and Value').length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText(/Best-in-class signature food platform/)).toBeInTheDocument()
        expect(
            screen.getByText(/Industry-leading customer perception of speed and value/)
        ).toBeInTheDocument()
    })
})
