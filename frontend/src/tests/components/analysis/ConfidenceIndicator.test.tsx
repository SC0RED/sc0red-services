import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import ConfidenceIndicator from '@/components/analysis/ConfidenceIndicator'

/**
 * Coverage focus: the indicator's visual contract (3-dot scale, single
 * neutral color, NO risk-tier palette) and its accessibility
 * contract (aria-label conveys the level; dots are aria-hidden).
 *
 * The "no risk-tier palette" check is the regression guard for UX
 * Audit 5 — the entire point of this component is that it avoids the
 * green/amber/red palette that's used for the page's risk-tier system.
 */

describe('ConfidenceIndicator', () => {
    function getDots(container: HTMLElement) {
        // The aria-hidden dots are direct children of the wrapper span.
        const wrapper = container.firstElementChild!
        return Array.from(wrapper.querySelectorAll('span[aria-hidden="true"]'))
    }

    function isFilled(dot: Element) {
        const bg = (dot as HTMLElement).style.background
        // Filled dots have a `var(--text-secondary)` background;
        // hollow dots have `transparent`.
        return bg.includes('text-secondary')
    }

    it('renders 3 filled + 0 hollow dots for HIGH', () => {
        const { container } = render(<ConfidenceIndicator confidence="HIGH" />)
        const dots = getDots(container)
        expect(dots).toHaveLength(3)
        expect(dots.filter(isFilled)).toHaveLength(3)
    })

    it('renders 2 filled + 1 hollow dots for MEDIUM', () => {
        const { container } = render(<ConfidenceIndicator confidence="MEDIUM" />)
        const dots = getDots(container)
        expect(dots).toHaveLength(3)
        expect(dots.filter(isFilled)).toHaveLength(2)
    })

    it('renders 1 filled + 2 hollow dots for LOW', () => {
        const { container } = render(<ConfidenceIndicator confidence="LOW" />)
        const dots = getDots(container)
        expect(dots).toHaveLength(3)
        expect(dots.filter(isFilled)).toHaveLength(1)
    })

    it('exposes "Confidence: High" as the accessible name for HIGH', () => {
        render(<ConfidenceIndicator confidence="HIGH" />)
        expect(screen.getByLabelText('Confidence: High')).toBeInTheDocument()
    })

    it('exposes "Confidence: Medium" as the accessible name for MEDIUM', () => {
        render(<ConfidenceIndicator confidence="MEDIUM" />)
        expect(screen.getByLabelText('Confidence: Medium')).toBeInTheDocument()
    })

    it('exposes "Confidence: Low" as the accessible name for LOW', () => {
        render(<ConfidenceIndicator confidence="LOW" />)
        expect(screen.getByLabelText('Confidence: Low')).toBeInTheDocument()
    })

    it('renders smaller dots in size="small" than in size="default"', () => {
        const { container: smallC } = render(<ConfidenceIndicator confidence="HIGH" size="small" />)
        const { container: defaultC } = render(<ConfidenceIndicator confidence="HIGH" size="default" />)
        const smallDot = getDots(smallC)[0] as HTMLElement
        const defaultDot = getDots(defaultC)[0] as HTMLElement
        // Width is set inline; small should be strictly less than default.
        const smallWidth = parseInt(smallDot.style.width, 10)
        const defaultWidth = parseInt(defaultDot.style.width, 10)
        expect(smallWidth).toBeLessThan(defaultWidth)
    })

    it('marks all dots as aria-hidden so screen readers announce only the wrapper label', () => {
        const { container } = render(<ConfidenceIndicator confidence="HIGH" />)
        const dots = getDots(container)
        for (const dot of dots) {
            expect(dot.getAttribute('aria-hidden')).toBe('true')
        }
    })

    it('attaches the long-form rationale tooltip on the default size variant', () => {
        const { container } = render(<ConfidenceIndicator confidence="HIGH" />)
        const wrapper = container.firstElementChild as HTMLElement
        // Native title attribute carries the rationale text.
        expect(wrapper.title).toMatch(/concrete public data/i)
    })

    it('does NOT attach the rationale tooltip on the small size variant', () => {
        // The small variant lives in chip headers where tooltip-on-hover
        // would compete with the surrounding chip's own hover affordance.
        const { container } = render(<ConfidenceIndicator confidence="HIGH" size="small" />)
        const wrapper = container.firstElementChild as HTMLElement
        expect(wrapper.title).toBe('')
    })

    it('does NOT use any risk-tier CSS variable (regression guard for Audit 5)', () => {
        // The whole point of this component is to NOT reuse the
        // risk-tier palette that the page already uses for low/moderate/
        // high/critical risk. If a future contributor reaches for
        // var(--risk-low) for "looks more important", this guard fails.
        const html = ['HIGH', 'MEDIUM', 'LOW']
            .map((level) => {
                const { container } = render(
                    <ConfidenceIndicator confidence={level as 'HIGH' | 'MEDIUM' | 'LOW'} />
                )
                return container.innerHTML
            })
            .join('\n')
        expect(html).not.toMatch(/--risk-low/)
        expect(html).not.toMatch(/--risk-moderate/)
        expect(html).not.toMatch(/--risk-high/)
        expect(html).not.toMatch(/--risk-critical/)
    })
})
