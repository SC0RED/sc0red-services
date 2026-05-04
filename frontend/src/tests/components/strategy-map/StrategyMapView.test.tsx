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

    it('renders the mission inside a closed <details> disclosure by default', () => {
        const { container } = render(<StrategyMapView strategyMap={fullStrategyMap} />)
        const details = container.querySelector('details')
        expect(details).not.toBeNull()
        // Closed disclosure — `open` attribute absent.
        expect(details?.hasAttribute('open')).toBe(false)
        // Summary label is the only mission-related text visible without opening.
        expect(screen.getByText(/Mission \(synthesised\)/)).toBeInTheDocument()
    })

    it('lists every strategic priority', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        // Both priorities from the fixture should appear as legend pills.
        expect(screen.getAllByText('Grow Through Foodservice').length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText('Deliver Convenience and Value').length).toBeGreaterThanOrEqual(1)
    })
})
