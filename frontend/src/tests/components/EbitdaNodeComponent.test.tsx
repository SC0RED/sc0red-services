/**
 * Component tests for the EBITDA tree node renderer (`EbitdaNodeComponent`).
 *
 * These tests focus on the parts of the component that don't require
 * ReactFlow's browser internals — specifically the chip-rendering logic and
 * the keyboard/screen-reader hooks for the new `confidence_level` /
 * `confidence_basis` fields. The full ReactFlow integration is exercised in
 * the page-level Playwright suite.
 *
 * The `Handle` calls inside the component need a ReactFlowProvider to avoid
 * crashing — we wrap with a thin provider stub via `@xyflow/react`'s named
 * `ReactFlowProvider`.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReactFlowProvider } from '@xyflow/react'

import EbitdaNodeComponent, { type EbitdaNodeData } from '@/components/EbitdaNodeComponent'

// ReactFlow uses ResizeObserver internally; jsdom doesn't ship it.
global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}))

function makeNodeProps(overrides: Partial<EbitdaNodeData> = {}) {
    const data: EbitdaNodeData = {
        label: 'Subscriptions',
        type: 'revenue',
        valueRange: '$8M-$40M',
        percentageOfParent: 80,
        description: 'SaaS subscription revenue',
        linkedOpportunities: [],
        ...overrides,
    }
    // The component takes the full xyflow NodeProps shape; we cast through
    // unknown because only `data` is read by the component under test.
    return {
        id: 'node-1',
        type: 'ebitdaNode',
        data,
        selected: false,
        dragging: false,
        zIndex: 0,
        isConnectable: false,
        positionAbsoluteX: 0,
        positionAbsoluteY: 0,
        sourcePosition: 'bottom',
        targetPosition: 'top',
    } as unknown as Parameters<typeof EbitdaNodeComponent>[0]
}

function renderNode(props: Parameters<typeof EbitdaNodeComponent>[0]) {
    return render(
        <ReactFlowProvider>
            <EbitdaNodeComponent {...props} />
        </ReactFlowProvider>
    )
}

describe('EbitdaNodeComponent — confidence chip', () => {
    it('renders a chip when confidenceLevel is high', () => {
        renderNode(makeNodeProps({ confidenceLevel: 'high', confidenceBasis: 'Test high.' }))
        const chip = screen.getByTestId('ebitda-confidence-chip')
        expect(chip).toBeInTheDocument()
        // ConfidenceIndicator renders an aria-label for the level
        const indicator = screen.getByLabelText('Confidence: High')
        expect(indicator).toBeInTheDocument()
    })

    it('renders a chip when confidenceLevel is medium', () => {
        renderNode(makeNodeProps({ confidenceLevel: 'medium', confidenceBasis: 'Test medium.' }))
        expect(screen.getByLabelText('Confidence: Medium')).toBeInTheDocument()
    })

    it('renders a chip when confidenceLevel is low', () => {
        renderNode(makeNodeProps({ confidenceLevel: 'low', confidenceBasis: 'Test low.' }))
        expect(screen.getByLabelText('Confidence: Low')).toBeInTheDocument()
    })

    it('suppresses the chip when confidenceLevel is null', () => {
        renderNode(makeNodeProps({ confidenceLevel: null, confidenceBasis: null }))
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })

    it('suppresses the chip when confidenceLevel is undefined', () => {
        renderNode(makeNodeProps({}))
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })

    it('suppresses the chip on subtotal nodes even if confidenceLevel is present', () => {
        // Defensive: the spec says rollups carry no confidence — backend
        // shouldn't emit it for subtotals — but the frontend filters anyway.
        renderNode(
            makeNodeProps({
                type: 'subtotal',
                confidenceLevel: 'high',
                confidenceBasis: 'Should not show on subtotals.',
            })
        )
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })

    it('suppresses the chip on margin nodes even if confidenceLevel is present', () => {
        renderNode(
            makeNodeProps({
                type: 'margin',
                confidenceLevel: 'high',
                confidenceBasis: 'Should not show on margin rollups.',
            })
        )
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })

    it('suppresses the chip when no value range is present (nothing to attach to)', () => {
        renderNode(makeNodeProps({ valueRange: undefined, confidenceLevel: 'high' }))
        // Chip lives inside the value-range row; without a value range, the
        // row doesn't render at all.
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })
})

describe('EbitdaNodeComponent — chip a11y', () => {
    it('exposes the basis via the title attribute for hover/focus tooltip', () => {
        renderNode(
            makeNodeProps({
                confidenceLevel: 'medium',
                confidenceBasis:
                    'Revenue derived from a SaaS template (matched on business model) ' +
                    'applied to a defaulted size bracket (no matching company-size signal).',
            })
        )
        const chip = screen.getByTestId('ebitda-confidence-chip')
        expect(chip.getAttribute('title')).toContain('Revenue derived from a SaaS template')
        expect(chip.getAttribute('title')).toContain('defaulted size bracket')
    })

    it('chip wrapper is keyboard focusable', () => {
        renderNode(makeNodeProps({ confidenceLevel: 'low', confidenceBasis: 'Both defaulted.' }))
        const chip = screen.getByTestId('ebitda-confidence-chip')
        expect(chip.getAttribute('tabindex')).toBe('0')
    })

    it('Tab moves focus to the chip', async () => {
        const user = userEvent.setup()
        renderNode(makeNodeProps({ confidenceLevel: 'high', confidenceBasis: 'Test.' }))
        const chip = screen.getByTestId('ebitda-confidence-chip')
        await user.tab()
        expect(chip).toHaveFocus()
    })

    it('omits the title attribute when basis is null', () => {
        renderNode(makeNodeProps({ confidenceLevel: 'high', confidenceBasis: null }))
        const chip = screen.getByTestId('ebitda-confidence-chip')
        expect(chip.getAttribute('title')).toBeNull()
    })
})
