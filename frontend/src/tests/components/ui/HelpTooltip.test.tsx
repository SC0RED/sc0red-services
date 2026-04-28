import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import HelpTooltip from '@/components/ui/HelpTooltip'
import { HELP_CONTENT } from '@/lib/help-content'

/**
 * Tests for the inline-help tooltip primitive used to surface PE-domain
 * explainers across the analyses table, analysis detail page, and
 * opportunities list.
 *
 * Coverage targets (per `webapp-ux-foundations-tier2` §2.6):
 *   - Renders on hover (pointer enter)
 *   - Renders on focus (keyboard tab)
 *   - Renders on click/tap (always-open, not toggle)
 *   - Content matches the `HELP_CONTENT` registry
 *   - Reduced-motion path: handled by the global CSS rule in `globals.css`
 *     (no per-component logic to test in JS)
 *   - A11y: role="tooltip" + aria-describedby association, aria-hidden
 *     mirrors visual state, popover stays in DOM (no mid-announcement
 *     unmount race for screen readers)
 *
 * The popover stays mounted at all times to avoid cutting off a screen
 * reader that's announcing the description on focus when the user Tabs
 * away. Visual state is exposed via the `data-state="open" | "closed"`
 * attribute, which tests assert on instead of DOM presence.
 */

function getTooltip() {
    // RTL excludes `aria-hidden` elements from accessibility queries by
    // default. The popover is `aria-hidden` while closed (intentionally,
    // so screen readers don't double-read it), so we opt in to hidden
    // matches. The `data-state` attribute is the canonical signal for
    // visual-state assertions.
    return screen.getByRole('tooltip', { hidden: true })
}

function isOpen(tooltip: HTMLElement): boolean {
    return tooltip.getAttribute('data-state') === 'open'
}

describe('HelpTooltip', () => {
    it('renders the trigger button with an accessible label', () => {
        render(<HelpTooltip term="risk_tier" />)
        expect(screen.getByRole('button', { name: /what is risk tier/i })).toBeInTheDocument()
        // Popover is always in the DOM but starts closed.
        expect(getTooltip()).toHaveAttribute('data-state', 'closed')
        expect(getTooltip()).toHaveAttribute('aria-hidden', 'true')
    })

    it('opens the popover on pointer enter', () => {
        render(<HelpTooltip term="risk_tier" />)
        const wrapper = screen.getByRole('button').parentElement!
        fireEvent.pointerEnter(wrapper)
        expect(isOpen(getTooltip())).toBe(true)
        expect(getTooltip()).toHaveAttribute('aria-hidden', 'false')
    })

    it('opens the popover on keyboard focus', () => {
        render(<HelpTooltip term="risk_tier" />)
        const trigger = screen.getByRole('button')
        trigger.focus()
        fireEvent.focus(trigger)
        expect(isOpen(getTooltip())).toBe(true)
    })

    it('opens (idempotently) on click — touch users tap, popover appears', async () => {
        // Click handler is always-open, never toggle. Toggling produced
        // flicker on touch devices that fire pointerEnter before click;
        // this test pins the always-open contract.
        const user = userEvent.setup()
        render(<HelpTooltip term="risk_tier" />)
        const trigger = screen.getByRole('button')

        await user.click(trigger)
        expect(isOpen(getTooltip())).toBe(true)

        // Second click is a no-op (popover already open).
        await user.click(trigger)
        expect(isOpen(getTooltip())).toBe(true)
    })

    it('renders the registry title and body', () => {
        // Content lives in the popover element regardless of open state —
        // it's just hidden when closed. Assert content directly.
        render(<HelpTooltip term="ebitda_tree" />)
        const tooltip = getTooltip()
        const expected = HELP_CONTENT.ebitda_tree
        expect(tooltip).toHaveTextContent(expected.title)
        expect(tooltip).toHaveTextContent(expected.body)
    })

    it('respects custom label override', () => {
        render(<HelpTooltip term="risk_tier" label="Tell me about tiers" />)
        expect(screen.getByRole('button', { name: 'Tell me about tiers' })).toBeInTheDocument()
    })

    it('associates the trigger with the popover via aria-describedby unconditionally', () => {
        // aria-describedby is set whether the popover is open or closed —
        // a screen reader on focus pulls the cached description from the
        // referenced element. `aria-hidden` and `data-state` together
        // signal whether the visual popover is active.
        render(<HelpTooltip term="value_lever" />)
        const trigger = screen.getByRole('button')
        const tooltip = getTooltip()

        expect(trigger.getAttribute('aria-describedby')).toBe(tooltip.id)
        expect(tooltip.id).toBeTruthy()

        fireEvent.focus(trigger)
        // Same association after open.
        expect(trigger.getAttribute('aria-describedby')).toBe(tooltip.id)
    })

    it('reflects open state in aria-expanded', () => {
        render(<HelpTooltip term="value_lever" />)
        const trigger = screen.getByRole('button')

        expect(trigger.getAttribute('aria-expanded')).toBe('false')
        fireEvent.focus(trigger)
        expect(trigger.getAttribute('aria-expanded')).toBe('true')
    })

    it('closes on Escape key when open', () => {
        render(<HelpTooltip term="industry" />)
        fireEvent.focus(screen.getByRole('button'))
        expect(isOpen(getTooltip())).toBe(true)

        fireEvent.keyDown(document, { key: 'Escape' })
        expect(isOpen(getTooltip())).toBe(false)
    })

    it('closes when clicking outside the trigger', () => {
        render(
            <div>
                <button type="button">Outside</button>
                <HelpTooltip term="impact_rating" />
            </div>
        )
        const trigger = screen.getByRole('button', { name: /what is impact/i })
        fireEvent.focus(trigger)
        expect(isOpen(getTooltip())).toBe(true)

        const outside = screen.getByRole('button', { name: 'Outside' })
        fireEvent.pointerDown(outside)
        expect(isOpen(getTooltip())).toBe(false)
    })

    it('keeps the popover open on pointer-leave when focus is still inside', () => {
        // Keyboard user tabs onto the icon (popover opens via focus). Mouse
        // happens to pass over the icon (pointerEnter fires) and then leaves
        // (pointerLeave fires). Without the focus-still-inside guard the
        // popover would yank closed under the keyboard user — bad UX.
        render(<HelpTooltip term="risk_score" />)
        const trigger = screen.getByRole('button')
        trigger.focus()
        fireEvent.focus(trigger)
        const wrapper = trigger.parentElement!
        fireEvent.pointerEnter(wrapper)
        fireEvent.pointerLeave(wrapper)

        expect(isOpen(getTooltip())).toBe(true)
    })

    it('keeps the popover element in the DOM at all times', () => {
        // Regression guard: the popover MUST stay mounted so a screen
        // reader announcement initiated on focus is not interrupted by
        // a mid-announcement unmount when the user Tabs away. Earlier
        // implementations conditionally rendered the popover; this test
        // pins the always-mounted contract.
        render(<HelpTooltip term="risk_tier" />)
        const tooltip = getTooltip()
        expect(tooltip).toBeInTheDocument()

        // After open + close, still in the DOM.
        const trigger = screen.getByRole('button')
        fireEvent.focus(trigger)
        fireEvent.keyDown(document, { key: 'Escape' })
        expect(getTooltip()).toBeInTheDocument()
        expect(getTooltip()).toHaveAttribute('data-state', 'closed')
    })

    it('renders all registry terms without crashing', () => {
        // Smoke test — guards against an enum/registry mismatch breaking
        // any wired surface. If a key in HELP_CONTENT renders to a missing
        // title or body, the assertion below fails.
        for (const term of Object.keys(HELP_CONTENT) as (keyof typeof HELP_CONTENT)[]) {
            const { unmount } = render(<HelpTooltip term={term} />)
            const tooltip = getTooltip()
            expect(tooltip).toHaveTextContent(HELP_CONTENT[term].title)
            unmount()
        }
    })
})
