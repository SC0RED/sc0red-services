/**
 * Component tests for the EBITDA renderer (``EbitdaNodeComponent``).
 *
 * The component branches on ``isSubtotalHeading`` between two
 * variants — a **band header** for P&L subtotals and a **compact chip**
 * for leaves under each subtotal. Component history:
 *
 *   - ``redesign-ebitda-impact-model`` stripped ``@xyflow/react``
 *     bindings (no more ``Handle`` / ``Position`` / ``NodeProps``).
 *   - ``compact-ebitda-bands`` split the body into ``BandHeader`` +
 *     ``LeafChip`` variants, deleted the absolutely-positioned hover
 *     overlay, and switched leaf hover detail to native ``title``.
 *
 * These tests cover:
 *   - Confidence chip rendering rules on the chip variant (per
 *     ``ebitda-tree-confidence``).
 *   - The confidence chip's keyboard + tooltip accessibility.
 *   - The opportunity-linked indicator dots.
 *   - Band-header surfaces (heading scale, colored left strip).
 *   - The no-custom-overlay regression guard for the leaf chip.
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

    it('Tab moves focus through the chip then to the confidence chip', async () => {
        const user = userEvent.setup()
        const { container } = render(
            <EbitdaNodeComponent {...makeProps({ confidenceLevel: 'high', confidenceBasis: 'Test.' })} />
        )
        const article = container.querySelector('article') as HTMLElement
        const confidenceChip = screen.getByTestId('ebitda-confidence-chip')
        // The outer ``<article>`` carries ``tabIndex={0}`` so the chip
        // is reachable by keyboard even when no confidence is present.
        // First Tab lands on the article; second Tab moves into the
        // nested confidence-chip wrapper.
        await user.tab()
        expect(article).toHaveFocus()
        await user.tab()
        expect(confidenceChip).toHaveFocus()
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

describe('EbitdaNodeComponent — band-header variant (isSubtotalHeading=true)', () => {
    it('renders the label inside an <h3> with a colored left-edge strip', () => {
        const { container } = render(
            <EbitdaNodeComponent
                {...makeProps({
                    label: 'Total Revenue',
                    type: 'revenue',
                    valueRange: '$15M-$200M',
                    isSubtotalHeading: true,
                })}
            />
        )
        // Label is inside <h3> so screen readers can navigate by heading.
        const heading = screen.getByRole('heading', { level: 3, name: 'Total Revenue' })
        expect(heading).toBeInTheDocument()
        // The band header's outer element carries the colored left strip.
        // Inline ``border-left`` styling is the spec contract — query for
        // an element whose style attribute contains a ``4px solid`` declaration.
        const styled = Array.from(container.querySelectorAll<HTMLElement>('*')).filter((el) =>
            /border-left\s*:\s*4px\s+solid/i.test(el.getAttribute('style') ?? '')
        )
        expect(styled.length).toBeGreaterThan(0)
    })

    it('surfaces the value range inline next to the label', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    label: 'Total Revenue',
                    type: 'revenue',
                    valueRange: '$15M-$200M',
                    isSubtotalHeading: true,
                })}
            />
        )
        expect(screen.getByText('$15M-$200M')).toBeInTheDocument()
    })

    it('does NOT render any chip-only surface in the band-header variant', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    type: 'revenue',
                    confidenceLevel: 'high',
                    linkedOpportunities: [{ title: 'X', valueLever: 'Revenue Side' }],
                    description: 'A description that would be a tooltip on the chip variant.',
                    isSubtotalHeading: true,
                })}
            />
        )
        // Band headers carry no confidence chip, no opportunity dots, no
        // tooltip description on the outer element — they're presentation-
        // only anchors for the band beneath them.
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
        expect(screen.queryByTestId('ebitda-linked-opportunity-dots')).toBeNull()
    })
})

describe('EbitdaNodeComponent — no custom hover overlay (compact-ebitda-bands)', () => {
    it("exposes the leaf description via the chip's native title attribute", () => {
        const { container } = render(
            <EbitdaNodeComponent
                {...makeProps({
                    description: 'Recurring subscription revenue across all tiers.',
                })}
            />
        )
        const article = container.querySelector('article')
        expect(article).not.toBeNull()
        expect(article!.getAttribute('title')).toBe('Recurring subscription revenue across all tiers.')
    })

    it('omits the title attribute when the description is empty', () => {
        const { container } = render(<EbitdaNodeComponent {...makeProps({ description: '' })} />)
        const article = container.querySelector('article')
        expect(article).not.toBeNull()
        expect(article!.hasAttribute('title')).toBe(false)
    })

    it('the chip is keyboard-focusable even without a confidence level', () => {
        // Per ``ebitda-impact-model`` spec: chips MUST be reachable in
        // keyboard tab order between the band header above and the next
        // connector below. The confidence chip's inner wrapper has its
        // own ``tabIndex={0}``, but a chip with no confidence level
        // would otherwise have zero focusable surface — the outer
        // ``<article>`` carries ``tabIndex={0}`` to guarantee
        // reachability in every leaf case.
        const { container } = render(
            <EbitdaNodeComponent
                {...makeProps({
                    confidenceLevel: null,
                    confidenceBasis: null,
                    linkedOpportunities: [],
                })}
            />
        )
        const article = container.querySelector('article')
        expect(article).not.toBeNull()
        expect(article!.getAttribute('tabindex')).toBe('0')
    })

    it('renders no element with position: absolute (no custom overlay)', () => {
        // Anti-regression guard: the prior overlay used
        // ``position: absolute; top: 100%`` and overflowed into the next
        // row. The compact-ebitda-bands change removed it; this test
        // pins the contract so a future contributor doesn't reintroduce
        // it by accident.
        const { container } = render(
            <EbitdaNodeComponent
                {...makeProps({
                    description: 'Some descriptive text.',
                    linkedOpportunities: [{ title: 'X', valueLever: 'Revenue Side' }],
                })}
            />
        )
        const offending = Array.from(container.querySelectorAll<HTMLElement>('*')).filter((el) =>
            /position\s*:\s*absolute/i.test(el.getAttribute('style') ?? '')
        )
        expect(offending).toHaveLength(0)
    })
})
