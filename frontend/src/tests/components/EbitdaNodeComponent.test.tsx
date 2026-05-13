/**
 * Component tests for the EBITDA card renderer (``EbitdaNodeComponent``).
 *
 * Phase 5 stripped this component of its ``@xyflow/react`` bindings
 * (no more ``Handle`` / ``Position`` / ``NodeProps``). It now takes
 * direct props and renders as a plain ``<article>``. These tests cover:
 *   - The confidence chip rendering rules (per ``ebitda-tree-confidence``).
 *   - The chip's keyboard + tooltip accessibility.
 *   - The opportunity-linked indicator dots.
 *   - The hover-description tooltip.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import EbitdaNodeComponent, { type EbitdaCardProps } from '@/components/EbitdaNodeComponent'

function makeProps(overrides: Partial<EbitdaCardProps> = {}): EbitdaCardProps {
    return {
        label: 'Subscriptions',
        type: 'revenue',
        valueRange: '$8M-$40M',
        percentageOfParent: 80,
        description: 'SaaS subscription revenue',
        linkedOpportunities: [],
        ...overrides,
    }
}

describe('EbitdaNodeComponent — confidence chip', () => {
    it('renders a chip when confidenceLevel is high', () => {
        render(
            <EbitdaNodeComponent {...makeProps({ confidenceLevel: 'high', confidenceBasis: 'Test high.' })} />
        )
        const chip = screen.getByTestId('ebitda-confidence-chip')
        expect(chip).toBeInTheDocument()
        // ConfidenceIndicator renders an aria-label for the level
        expect(screen.getByLabelText('Confidence: High')).toBeInTheDocument()
    })

    it('renders a chip when confidenceLevel is medium', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({ confidenceLevel: 'medium', confidenceBasis: 'Test medium.' })}
            />
        )
        expect(screen.getByLabelText('Confidence: Medium')).toBeInTheDocument()
    })

    it('renders a chip when confidenceLevel is low', () => {
        render(
            <EbitdaNodeComponent {...makeProps({ confidenceLevel: 'low', confidenceBasis: 'Test low.' })} />
        )
        expect(screen.getByLabelText('Confidence: Low')).toBeInTheDocument()
    })

    it('suppresses the chip when confidenceLevel is null', () => {
        render(<EbitdaNodeComponent {...makeProps({ confidenceLevel: null, confidenceBasis: null })} />)
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })

    it('suppresses the chip when confidenceLevel is undefined', () => {
        render(<EbitdaNodeComponent {...makeProps({})} />)
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })

    it('suppresses the chip on subtotal nodes even if confidenceLevel is present', () => {
        // Defensive: the spec says rollups carry no confidence — backend
        // shouldn't emit it for subtotals — but the frontend filters anyway.
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    type: 'subtotal',
                    confidenceLevel: 'high',
                    confidenceBasis: 'Should not show on subtotals.',
                })}
            />
        )
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })

    it('suppresses the chip on margin nodes even if confidenceLevel is present', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    type: 'margin',
                    confidenceLevel: 'high',
                    confidenceBasis: 'Should not show on margin rollups.',
                })}
            />
        )
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })

    it('suppresses the chip when no value range is present (nothing to attach to)', () => {
        render(<EbitdaNodeComponent {...makeProps({ valueRange: undefined, confidenceLevel: 'high' })} />)
        // Chip lives inside the value-range row; without a value range, the
        // row doesn't render at all.
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
    })
})

describe('EbitdaNodeComponent — chip a11y', () => {
    it('exposes the basis via the title attribute for hover/focus tooltip', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    confidenceLevel: 'medium',
                    confidenceBasis:
                        'Revenue derived from a SaaS template (matched on business model) ' +
                        'applied to a defaulted size bracket (no matching company-size signal).',
                })}
            />
        )
        const chip = screen.getByTestId('ebitda-confidence-chip')
        expect(chip.getAttribute('title')).toContain('Revenue derived from a SaaS template')
        expect(chip.getAttribute('title')).toContain('defaulted size bracket')
    })

    it('chip wrapper is keyboard focusable', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({ confidenceLevel: 'low', confidenceBasis: 'Both defaulted.' })}
            />
        )
        const chip = screen.getByTestId('ebitda-confidence-chip')
        expect(chip.getAttribute('tabindex')).toBe('0')
    })

    it('Tab moves focus to the chip', async () => {
        const user = userEvent.setup()
        render(<EbitdaNodeComponent {...makeProps({ confidenceLevel: 'high', confidenceBasis: 'Test.' })} />)
        const chip = screen.getByTestId('ebitda-confidence-chip')
        await user.tab()
        expect(chip).toHaveFocus()
    })

    it('omits the title attribute when basis is null', () => {
        render(<EbitdaNodeComponent {...makeProps({ confidenceLevel: 'high', confidenceBasis: null })} />)
        const chip = screen.getByTestId('ebitda-confidence-chip')
        expect(chip.getAttribute('title')).toBeNull()
    })
})

describe('EbitdaNodeComponent — opportunity-link affordance', () => {
    it('renders one indicator dot per linked opportunity', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    linkedOpportunities: [
                        { title: 'Upsell tier', valueLever: 'Revenue Side' },
                        { title: 'Trim support costs', valueLever: 'Cost Side' },
                    ],
                })}
            />
        )
        const dotRow = screen.getByTestId('ebitda-linked-opportunity-dots')
        // One child per linked opportunity.
        expect(dotRow.children).toHaveLength(2)
    })

    it('attaches an opportunity title via the dot title attribute', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    linkedOpportunities: [{ title: 'Upsell tier', valueLever: 'Revenue Side' }],
                })}
            />
        )
        const dotRow = screen.getByTestId('ebitda-linked-opportunity-dots')
        const dot = dotRow.firstElementChild as HTMLElement
        expect(dot.getAttribute('title')).toBe('Upsell tier (Revenue Side)')
    })

    it('omits the dot row entirely when no opportunities are linked', () => {
        render(<EbitdaNodeComponent {...makeProps({ linkedOpportunities: [] })} />)
        expect(screen.queryByTestId('ebitda-linked-opportunity-dots')).toBeNull()
    })
})
