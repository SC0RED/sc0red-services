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
 *   - ``redesign-analysis-visuals`` P2 removed the confidence chip
 *     (the data still flows on ``EbitdaNode`` for any future surface,
 *     but the visual is gone — the opportunity-link dot strip is the
 *     remaining inline signal) and migrated the inline dot loop to
 *     the shared ``OpportunityDotStrip`` component.
 *
 * These tests cover:
 *   - Opportunity-link dot strip rendering (delegated to the shared
 *     ``OpportunityDotStrip`` — basic presence here, full overflow /
 *     accessibility coverage lives in that component's test file).
 *   - Band-header surfaces (heading scale, colored left strip).
 *   - The no-custom-overlay regression guard for the leaf chip.
 *   - Neutral body + colored-left-edge invariant.
 *   - Type-scale invariant (font sizes on the canonical step set).
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import EbitdaNodeComponent, { type EbitdaCardProps } from '@/components/EbitdaNodeComponent'
import type { Opportunity } from '@/lib/types/api'

function makeOpportunity(overrides: Partial<Opportunity> = {}): Opportunity {
    return {
        title: 'Opportunity title',
        description: 'desc',
        impact_rating: 'High',
        timeline: 'Quick Win (1-3 months)',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Revenue Side',
        ...overrides,
    }
}

function makeProps(overrides: Partial<EbitdaCardProps> = {}): EbitdaCardProps {
    return {
        label: 'Subscriptions',
        type: 'revenue',
        valueRange: '$8M-$40M',
        percentageOfParent: 80,
        description: 'SaaS subscription revenue',
        linkedIndices: [],
        opportunities: [],
        ...overrides,
    }
}

describe('EbitdaNodeComponent — opportunity-link affordance', () => {
    it('renders one indicator dot per linked opportunity', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    linkedIndices: [0, 1],
                    opportunities: [
                        makeOpportunity({ title: 'Upsell tier', value_lever: 'Revenue Side' }),
                        makeOpportunity({ title: 'Trim support costs', value_lever: 'Cost Side' }),
                    ],
                })}
            />
        )
        const dotRow = screen.getByTestId('ebitda-linked-opportunity-dots')
        // The strip renders `role="img"` with an aria-label summary; the
        // visible dots are aria-hidden children. Two indices → two dots.
        const dots = dotRow.querySelectorAll('span[aria-hidden="true"]')
        expect(dots).toHaveLength(2)
    })

    it('attaches an opportunity title + lever via each dot title attribute', () => {
        render(
            <EbitdaNodeComponent
                {...makeProps({
                    linkedIndices: [0],
                    opportunities: [makeOpportunity({ title: 'Upsell tier', value_lever: 'Revenue Side' })],
                })}
            />
        )
        const dotRow = screen.getByTestId('ebitda-linked-opportunity-dots')
        const dot = dotRow.querySelector('span[aria-hidden="true"]')
        expect(dot?.getAttribute('title')).toBe('Upsell tier (Revenue Side)')
    })

    it('omits the dot row entirely when no opportunities are linked', () => {
        render(
            <EbitdaNodeComponent {...makeProps({ linkedIndices: [], opportunities: [makeOpportunity()] })} />
        )
        expect(screen.queryByTestId('ebitda-linked-opportunity-dots')).toBeNull()
    })

    it('does not render the legacy confidence chip', () => {
        // Anti-regression: the chip was removed in
        // ``redesign-analysis-visuals`` P2 because Zack flagged it as
        // competing with the more decision-relevant opportunity dots.
        // The data still flows on ``EbitdaNode`` for any future surface
        // but no chip should render here.
        render(<EbitdaNodeComponent {...makeProps()} />)
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
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
        const heading = screen.getByRole('heading', { level: 3, name: 'Total Revenue' })
        expect(heading).toBeInTheDocument()
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
                    linkedIndices: [0],
                    opportunities: [makeOpportunity({ title: 'X', value_lever: 'Revenue Side' })],
                    description: 'A description that would be a tooltip on the chip variant.',
                    isSubtotalHeading: true,
                })}
            />
        )
        // Band headers carry no opportunity dots, no tooltip description on
        // the outer element — they're presentation-only anchors for the
        // band beneath them.
        expect(screen.queryByTestId('ebitda-linked-opportunity-dots')).toBeNull()
    })
})

describe('EbitdaNodeComponent — no custom hover overlay (compact-ebitda-bands)', () => {
    it("exposes the leaf description via the chip label's native title attribute (empty linkage)", () => {
        // Phase 13 of redesign-analysis-visuals wraps the chip in a
        // ``SourceLinkedOpportunitiesPopover``. When the chip has
        // linked opportunities, the popover surfaces them on hover —
        // the native ``title`` would compete with that popover, so it
        // moves to the inner label and only renders when there is NO
        // linked-opportunity popover to display.
        const { getByTestId } = render(
            <EbitdaNodeComponent
                {...makeProps({
                    description: 'Recurring subscription revenue across all tiers.',
                    linkedIndices: [],
                })}
            />
        )
        const label = getByTestId('ebitda-leaf-chip-label')
        expect(label.getAttribute('title')).toBe('Recurring subscription revenue across all tiers.')
    })

    it('omits the title attribute when the description is empty', () => {
        const { getByTestId } = render(<EbitdaNodeComponent {...makeProps({ description: '' })} />)
        const label = getByTestId('ebitda-leaf-chip-label')
        expect(label.hasAttribute('title')).toBe(false)
    })

    it('omits the title attribute when the chip has linked opportunities (popover takes over)', () => {
        // When the popover is the hover surface, the native title
        // would render on top of it. Skip the title in that case —
        // the popover already exposes the same context (and more).
        const { getByTestId } = render(
            <EbitdaNodeComponent
                {...makeProps({
                    description: 'Recurring subscription revenue.',
                    linkedIndices: [0],
                    opportunities: [makeOpportunity({ title: 'Roll out SKU', value_lever: 'Revenue Side' })],
                })}
            />
        )
        const label = getByTestId('ebitda-leaf-chip-label')
        expect(label.hasAttribute('title')).toBe(false)
    })

    it('the chip is keyboard-focusable even with no opportunity dots', () => {
        // Per ``ebitda-impact-model`` spec: chips MUST be reachable in
        // keyboard tab order between the band header above and the next
        // connector below. Phase 13 moved the focusable surface from
        // ``<article>`` to the ``SourceLinkedOpportunitiesPopover``
        // wrapper (a ``<div>`` carrying ``tabIndex={0}``). Same
        // keyboard-reachability guarantee, different tag.
        const { getByTestId } = render(<EbitdaNodeComponent {...makeProps({ linkedIndices: [] })} />)
        const chip = getByTestId('ebitda-leaf-chip')
        expect(chip.getAttribute('tabindex')).toBe('0')
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
                    linkedIndices: [0],
                    opportunities: [makeOpportunity({ title: 'X', value_lever: 'Revenue Side' })],
                })}
            />
        )
        const offending = Array.from(container.querySelectorAll<HTMLElement>('*')).filter((el) =>
            /position\s*:\s*absolute/i.test(el.getAttribute('style') ?? '')
        )
        expect(offending).toHaveLength(0)
    })
})

describe('EbitdaNodeComponent — neutral body + colored-left-edge (tighten-analysis-page-readability)', () => {
    it('renders the leaf chip with neutral body and a 3px colored left border', () => {
        const { container } = render(
            <EbitdaNodeComponent {...makeProps({ type: 'revenue', label: 'Subscriptions' })} />
        )
        const article = container.querySelector('[data-testid="ebitda-leaf-chip"]')
        expect(article).not.toBeNull()
        const style = article!.getAttribute('style') ?? ''
        expect(/border-left\s*:\s*3px\s+solid/i.test(style)).toBe(true)
        expect(style).toMatch(/background:\s*var\(--bg-surface-2\)/i)
        expect(style).toMatch(/border:\s*1px\s+solid\s+var\(--border-subtle\)/i)
        const label = article!.querySelector('div') as HTMLElement
        const labelStyle = label.getAttribute('style') ?? ''
        expect(labelStyle).toMatch(/color:\s*var\(--text-primary\)/i)
        expect(label.textContent).toContain('Subscriptions')
    })

    it('does NOT bathe the chip in semantic color (anywhere — outer or descendant)', () => {
        const { container } = render(<EbitdaNodeComponent {...makeProps({ type: 'revenue' })} />)
        const article = container.querySelector('[data-testid="ebitda-leaf-chip"]') as HTMLElement
        const styled: HTMLElement[] = [
            article,
            ...Array.from(article.querySelectorAll<HTMLElement>('[style]')),
        ]
        for (const el of styled) {
            const style = (el.getAttribute('style') ?? '').toLowerCase()
            const stripped = style.replace(/border-left:[^;]+;?/g, '')
            expect(stripped).not.toContain('rgba(')
        }
    })

    it("renders each leaf type's accent on the 3px left border (revenue + cost)", () => {
        const accents: Array<{ type: 'revenue' | 'cost'; rgb: string }> = [
            { type: 'revenue', rgb: 'rgb(34, 197, 94)' },
            { type: 'cost', rgb: 'rgb(239, 68, 68)' },
        ]
        for (const { type, rgb } of accents) {
            const { container, unmount } = render(<EbitdaNodeComponent {...makeProps({ type })} />)
            const article = container.querySelector('[data-testid="ebitda-leaf-chip"]')
            const style = (article!.getAttribute('style') ?? '').toLowerCase()
            expect(style).toContain(`border-left: 3px solid ${rgb}`)
            unmount()
        }
    })
})

describe('EbitdaNodeComponent — type-scale invariant (tighten-analysis-page-readability)', () => {
    const CANONICAL = new Set(['0.75rem', '0.875rem', '1rem', '1.125rem', '1.5rem'])

    it('every inline fontSize on a rendered leaf chip is on the canonical scale', () => {
        const { container } = render(
            <EbitdaNodeComponent
                {...makeProps({
                    linkedIndices: [0],
                    opportunities: [makeOpportunity({ title: 'X', value_lever: 'Revenue Side' })],
                })}
            />
        )
        for (const el of Array.from(container.querySelectorAll<HTMLElement>('[style]'))) {
            const size = el.style.fontSize
            if (!size || !size.endsWith('rem')) continue
            expect(CANONICAL).toContain(size)
        }
    })

    it('every inline fontSize on a rendered band header is on the canonical scale', () => {
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
        for (const el of Array.from(container.querySelectorAll<HTMLElement>('[style]'))) {
            const size = el.style.fontSize
            if (!size || !size.endsWith('rem')) continue
            expect(CANONICAL).toContain(size)
        }
    })
})
