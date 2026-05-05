import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

// Mock @xyflow/react before importing the component so the `NodeToolbar`
// passthrough is in place when `StrategyMapNode` is loaded.
//
// Why mock at all: in production `NodeToolbar` portals its children
// through React Flow's internal store, which only contains nodes that
// React Flow itself has rendered (via `<ReactFlow nodes={[...]}/>`).
// Standalone test renders never populate that store, so the production
// `NodeToolbar` returns null unconditionally — making it impossible to
// assert tooltip content without spinning up a full ReactFlow canvas
// (which jsdom can't lay out — see EbitdaTree.test.tsx for the same
// constraint). The mock renders children as a plain `<div>` when
// `isVisible` is true, restoring testability.
//
// The mock attaches `data-toolbar-position` so tests can also assert
// which side of the chip the tooltip would render on (the capacity-band
// chips flip to `Position.Top` to avoid overflowing past the canvas
// bottom — see `StrategyMapNode.tsx`).
vi.mock('@xyflow/react', async () => {
    const actual = await vi.importActual<typeof import('@xyflow/react')>('@xyflow/react')
    return {
        ...actual,
        NodeToolbar: ({
            isVisible,
            children,
            position,
        }: {
            isVisible?: boolean
            children?: ReactNode
            position?: string
        }) =>
            isVisible ? (
                <div data-testid="strategy-map-node-toolbar" data-toolbar-position={position}>
                    {children}
                </div>
            ) : null,
    }
})

import { ReactFlowProvider } from '@xyflow/react'

import StrategyMapNode from '@/components/strategy-map/StrategyMapNode'
import type { StrategyMapNodeData } from '@/lib/strategyMap/layout'

// React Flow's <Handle> registers store listeners and requires a
// `ReactFlowProvider` ancestor; without it, every render throws "[React
// Flow]: Seems like you have not used zustand provider as an ancestor."
// Tests don't exercise the provider's behaviour — they just need it
// present in the tree.
const renderInProvider = (ui: ReactNode) => render(<ReactFlowProvider>{ui}</ReactFlowProvider>)

/**
 * `StrategyMapNode` is a React Flow custom node. It expects the
 * `NodeProps` shape but in tests we render it directly with a synthetic
 * props object — React Flow's runtime handles (top/bottom Handles)
 * render harmlessly outside a ReactFlowProvider in tests because they
 * only register listeners.
 */

const baseData: StrategyMapNodeData = {
    objectiveId: 'F1',
    perspective: 'financial',
    title: 'Grow profitable revenue across markets',
    definition: 'We will grow same-segment revenue by deepening engagement with current customers.',
    confidence: 'HIGH',
    rationaleSource: null,
    customerVoice: false,
    inSharedLane: false,
}

// Minimal NodeProps stub. Many fields are unused by the component so we
// cast to the bits we care about; the component reads `data` and `selected`.
const nodeProps = (overrides: Partial<{ data: StrategyMapNodeData; selected: boolean }> = {}) =>
    ({
        id: (overrides.data ?? baseData).objectiveId,
        data: overrides.data ?? baseData,
        selected: overrides.selected ?? false,
        type: 'strategyMap',
        zIndex: 0,
        isConnectable: false,
        positionAbsoluteX: 0,
        positionAbsoluteY: 0,
        dragging: false,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
    }) as any

describe('StrategyMapNode — default chip state', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('renders the objective ID and the title', () => {
        renderInProvider(<StrategyMapNode {...nodeProps()} />)
        expect(screen.getByText('F1')).toBeInTheDocument()
        expect(screen.getByText(/Grow profitable revenue/)).toBeInTheDocument()
    })

    it('does not render the full definition until hover', () => {
        renderInProvider(<StrategyMapNode {...nodeProps()} />)
        expect(screen.queryByText(/We will grow same-segment revenue/)).toBeNull()
    })

    it('exposes role=button + aria-label for screen readers', () => {
        renderInProvider(<StrategyMapNode {...nodeProps()} />)
        const node = screen.getByRole('button', {
            name: 'F1: Grow profitable revenue across markets',
        })
        expect(node).toBeInTheDocument()
    })
})

describe('StrategyMapNode — hover surfaces tooltip', () => {
    it('surfaces the full definition + ConfidenceChip when hovered', () => {
        renderInProvider(<StrategyMapNode {...nodeProps()} />)
        const node = screen.getByRole('button')
        fireEvent.mouseEnter(node)

        expect(screen.getByRole('tooltip')).toBeInTheDocument()
        expect(screen.getByText(/We will grow same-segment revenue/)).toBeInTheDocument()
        // The ConfidenceChip renders the literal label.
        expect(screen.getAllByText('HIGH').length).toBeGreaterThan(0)
    })

    it('shows the rationale_source when supplied', () => {
        const data: StrategyMapNodeData = {
            ...baseData,
            rationaleSource: 'EBITDA tree revenue branch.',
        }
        renderInProvider(<StrategyMapNode {...nodeProps({ data })} />)
        fireEvent.mouseEnter(screen.getByRole('button'))
        expect(screen.getByText(/Source: EBITDA tree revenue branch/)).toBeInTheDocument()
    })

    it('hides the tooltip when the pointer leaves', () => {
        renderInProvider(<StrategyMapNode {...nodeProps()} />)
        const node = screen.getByRole('button')
        fireEvent.mouseEnter(node)
        expect(screen.getByRole('tooltip')).toBeInTheDocument()
        fireEvent.mouseLeave(node)
        expect(screen.queryByRole('tooltip')).toBeNull()
    })

    it('treats React Flow `selected` (touch tap) the same as hover', () => {
        renderInProvider(<StrategyMapNode {...nodeProps({ selected: true })} />)
        // No mouseEnter — selected alone should expose the tooltip.
        expect(screen.getByRole('tooltip')).toBeInTheDocument()
        expect(screen.getByText(/We will grow same-segment revenue/)).toBeInTheDocument()
    })
})

describe('StrategyMapNode — confidence dot palette', () => {
    it('renders dot in --risk-low for HIGH', () => {
        renderInProvider(<StrategyMapNode {...nodeProps()} />)
        const dot = screen.getByTitle('Confidence: HIGH')
        expect(dot).toHaveStyle({ background: 'var(--risk-low)' })
    })

    it('renders dot in --risk-moderate for MEDIUM', () => {
        const data: StrategyMapNodeData = { ...baseData, confidence: 'MEDIUM' }
        renderInProvider(<StrategyMapNode {...nodeProps({ data })} />)
        const dot = screen.getByTitle('Confidence: MEDIUM')
        expect(dot).toHaveStyle({ background: 'var(--risk-moderate)' })
    })

    it('renders dot in --risk-high for LOW', () => {
        const data: StrategyMapNodeData = { ...baseData, confidence: 'LOW' }
        renderInProvider(<StrategyMapNode {...nodeProps({ data })} />)
        const dot = screen.getByTitle('Confidence: LOW')
        expect(dot).toHaveStyle({ background: 'var(--risk-high)' })
    })
})

describe('StrategyMapNode — customer-voice formatting', () => {
    it('wraps the title in curly quotes for customerVoice chips', () => {
        const data: StrategyMapNodeData = {
            ...baseData,
            objectiveId: 'C1',
            perspective: 'customer',
            customerVoice: true,
            title: 'Offer me fresh products',
        }
        renderInProvider(<StrategyMapNode {...nodeProps({ data })} />)
        // Curly quote marks bracket the rendered title.
        expect(screen.getAllByText(/“Offer me fresh products”/).length).toBeGreaterThan(0)
    })

    it('renders capacity chips with their bucket label', () => {
        const data: StrategyMapNodeData = {
            ...baseData,
            objectiveId: 'O.P',
            perspective: 'capacity',
            capacityBucket: 'People',
        }
        renderInProvider(<StrategyMapNode {...nodeProps({ data })} />)
        expect(screen.getByText('People')).toBeInTheDocument()
    })
})

describe('StrategyMapNode — shared-lane visual marker', () => {
    /**
     * Centre-lane chips (those the layout helper couldn't anchor to a
     * theme column) get a dashed left-border instead of solid so the
     * reader spots them at a glance. Behaviour disappears under the
     * planned `β` follow-up where every objective has a deterministic
     * theme.
     */
    it('renders solid left-border for chips with a real theme column', () => {
        renderInProvider(<StrategyMapNode {...nodeProps()} />)
        const node = screen.getByRole('button')
        expect(node).toHaveStyle({ borderLeft: '3px solid var(--accent-blue)' })
    })

    it('renders dashed left-border for chips in the shared centre lane', () => {
        const data: StrategyMapNodeData = { ...baseData, inSharedLane: true }
        renderInProvider(<StrategyMapNode {...nodeProps({ data })} />)
        const node = screen.getByRole('button')
        expect(node).toHaveStyle({ borderLeft: '3px dashed var(--accent-blue)' })
    })
})

describe('StrategyMapNode — tooltip max-height (long-definition overflow)', () => {
    /**
     * Production data surfaced a chip with a multi-paragraph definition
     * (~600 chars). The tooltip's intrinsic height extended past the
     * canvas's bottom edge AND past the bottom of the page section,
     * overlaying the gaps panel beneath. Bounded the wrapper at 320 px
     * with internal scroll so the UI is consistent regardless of how
     * verbose the AI was.
     */
    it('caps the tooltip wrapper at maxHeight: 320', () => {
        renderInProvider(<StrategyMapNode {...nodeProps()} />)
        fireEvent.mouseEnter(screen.getByRole('button'))
        const tooltip = screen.getByRole('tooltip')
        expect(tooltip).toHaveStyle({ maxHeight: '320px' })
    })
})

describe('StrategyMapNode — tooltip side flips for the bottom band', () => {
    /**
     * The strategy-map canvas has 4 horizontal perspective bands; the
     * Capacity band is the bottom one. A NodeToolbar with the default
     * `Position.Bottom` would render below the chip, which on a capacity
     * chip means below the canvas's bottom edge — overlaying the gaps
     * panel and CTA underneath. Capacity chips flip the tooltip to
     * `Position.Top` so the toolbar renders above the chip, inside the
     * canvas's vertical range.
     */
    it('uses Position.Bottom for chips in financial / customer / internal bands', () => {
        for (const perspective of ['financial', 'customer', 'internal'] as const) {
            const data: StrategyMapNodeData = { ...baseData, perspective }
            const { unmount } = renderInProvider(<StrategyMapNode {...nodeProps({ data })} />)
            fireEvent.mouseEnter(screen.getByRole('button'))
            const toolbar = screen.getByTestId('strategy-map-node-toolbar')
            expect(toolbar.getAttribute('data-toolbar-position')).toBe('bottom')
            unmount()
        }
    })

    it('uses Position.Top for capacity chips (avoids overflowing past canvas bottom)', () => {
        const data: StrategyMapNodeData = {
            ...baseData,
            objectiveId: 'O.P',
            perspective: 'capacity',
            capacityBucket: 'People',
        }
        renderInProvider(<StrategyMapNode {...nodeProps({ data })} />)
        fireEvent.mouseEnter(screen.getByRole('button'))
        const toolbar = screen.getByTestId('strategy-map-node-toolbar')
        expect(toolbar.getAttribute('data-toolbar-position')).toBe('top')
    })
})
