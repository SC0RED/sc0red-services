import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, it, expect, vi } from 'vitest'

import ExpandableCard from '@/components/ui/ExpandableCard'

/**
 * Coverage focus: the prop contract of ExpandableCard.
 *   - Controlled vs uncontrolled mode (detection by `isOpen !== undefined`)
 *   - ARIA: `aria-expanded` reflects state, `aria-controls` references
 *     the body's id, body always in DOM (uses `hidden` attribute, not
 *     conditional rendering)
 *   - Chevron rotation: `data-open` attribute reflects state
 *   - Header content + body content render in correct slots
 *   - Single-open accordion semantics work via the controlled API
 */

describe('ExpandableCard', () => {
    describe('uncontrolled mode', () => {
        it('starts closed by default', () => {
            render(
                <ExpandableCard id="x" header="Header text">
                    <div>body content</div>
                </ExpandableCard>
            )
            const trigger = screen.getByRole('button')
            expect(trigger).toHaveAttribute('aria-expanded', 'false')
        })

        it('toggles open on click', () => {
            render(
                <ExpandableCard id="x" header="Header text">
                    <div>body content</div>
                </ExpandableCard>
            )
            const trigger = screen.getByRole('button')
            fireEvent.click(trigger)
            expect(trigger).toHaveAttribute('aria-expanded', 'true')
            fireEvent.click(trigger)
            expect(trigger).toHaveAttribute('aria-expanded', 'false')
        })
    })

    describe('controlled mode', () => {
        it('uses the parent isOpen as the source of truth', () => {
            const { rerender } = render(
                <ExpandableCard id="x" isOpen={false} onToggle={vi.fn()} header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false')

            rerender(
                <ExpandableCard id="x" isOpen={true} onToggle={vi.fn()} header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
        })

        it('calls onToggle exactly once per click WITHOUT flipping aria-expanded until parent decides', () => {
            const onToggle = vi.fn()
            render(
                <ExpandableCard id="x" isOpen={false} onToggle={onToggle} header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            const trigger = screen.getByRole('button')
            fireEvent.click(trigger)
            // Parent's onToggle was called.
            expect(onToggle).toHaveBeenCalledTimes(1)
            // But aria-expanded did NOT flip — the parent still says false.
            expect(trigger).toHaveAttribute('aria-expanded', 'false')
        })

        it('treats isOpen={false} as controlled (not the same as undefined)', () => {
            // The detection rule is `isOpen !== undefined`. A controlled
            // parent passing `false` explicitly should NOT fall back to
            // internal state.
            const onToggle = vi.fn()
            render(
                <ExpandableCard id="x" isOpen={false} onToggle={onToggle} header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            const trigger = screen.getByRole('button')
            fireEvent.click(trigger)
            // Click does NOT toggle internal state — controlled mode delegates to parent.
            expect(trigger).toHaveAttribute('aria-expanded', 'false')
        })
    })

    describe('aria contract', () => {
        it('aria-controls references the body element id', () => {
            render(
                <ExpandableCard id="my-card" header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            const trigger = screen.getByRole('button')
            const ariaControls = trigger.getAttribute('aria-controls')
            expect(ariaControls).toBeTruthy()
            // The body element with that id exists in the DOM.
            expect(document.getElementById(ariaControls!)).not.toBeNull()
        })

        it('sanitises ids with spaces so aria-controls IDREFS parsing works', () => {
            // CRITICAL a11y regression caught by architecture-reviewer:
            // `aria-controls` is parsed as a SPACE-DELIMITED LIST of IDREFs
            // by assistive technologies. A caller passing
            // `id="Deploy AI Chatbot"` (e.g. from `opp.title`) would
            // otherwise produce an `aria-controls` value that screen
            // readers split into 3 separate IDREFs, none of which exist
            // — silently breaking the accordion relationship.
            //
            // ExpandableCard sanitises the `id` internally: spaces become
            // hyphens, and any non-id-grammar character is stripped. The
            // resulting bodyId contains NO whitespace.
            render(
                <ExpandableCard id="Deploy AI Chatbot" header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            const trigger = screen.getByRole('button')
            const ariaControls = trigger.getAttribute('aria-controls')!
            // The aria-controls value contains no whitespace.
            expect(ariaControls).not.toMatch(/\s/)
            // The body element with that exact id exists.
            expect(document.getElementById(ariaControls)).not.toBeNull()
        })

        it('strips characters outside the HTML5 id-token grammar', () => {
            // Special chars like `/`, `&`, `?`, `(`, `)` that could appear
            // in arbitrary opportunity titles also get stripped.
            render(
                <ExpandableCard id="Cost (50%) / Revenue & ROI" header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            const trigger = screen.getByRole('button')
            const ariaControls = trigger.getAttribute('aria-controls')!
            // Only valid id-grammar chars remain.
            expect(ariaControls).toMatch(/^[a-zA-Z0-9\-_:.]+$/)
            // Element with the resulting id exists.
            expect(document.getElementById(ariaControls)).not.toBeNull()
        })

        it('keeps body in DOM with hidden attribute when closed (so aria-controls reference stays valid)', () => {
            render(
                <ExpandableCard id="x" header="H">
                    <div data-testid="body">body</div>
                </ExpandableCard>
            )
            // Body is in the DOM even though closed.
            const body = screen.getByTestId('body')
            expect(body).toBeInTheDocument()
            // The wrapping body element carries the `hidden` attribute when closed.
            const wrapper = body.parentElement!
            expect(wrapper.hasAttribute('hidden')).toBe(true)
        })

        it('removes hidden attribute when open', () => {
            render(
                <ExpandableCard id="x" isOpen={true} onToggle={vi.fn()} header="H">
                    <div data-testid="body">body</div>
                </ExpandableCard>
            )
            const wrapper = screen.getByTestId('body').parentElement!
            expect(wrapper.hasAttribute('hidden')).toBe(false)
        })
    })

    describe('chevron rotation', () => {
        it('chevron data-open="false" when closed', () => {
            const { container } = render(
                <ExpandableCard id="x" header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            const chevron = container.querySelector('.expandable-card__chevron')
            expect(chevron).not.toBeNull()
            expect(chevron!.getAttribute('data-open')).toBe('false')
        })

        it('chevron data-open="true" when open', () => {
            const { container } = render(
                <ExpandableCard id="x" isOpen={true} onToggle={vi.fn()} header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            const chevron = container.querySelector('.expandable-card__chevron')
            expect(chevron!.getAttribute('data-open')).toBe('true')
        })

        it('chevron is aria-hidden so screen readers announce only the trigger', () => {
            const { container } = render(
                <ExpandableCard id="x" header="H">
                    <div>body</div>
                </ExpandableCard>
            )
            const chevron = container.querySelector('.expandable-card__chevron')
            expect(chevron!.getAttribute('aria-hidden')).toBe('true')
        })
    })

    describe('content placement', () => {
        it('renders header content inside the trigger button', () => {
            render(
                <ExpandableCard id="x" header={<span data-testid="hdr">Header text</span>}>
                    <div>body</div>
                </ExpandableCard>
            )
            const trigger = screen.getByRole('button')
            const hdr = screen.getByTestId('hdr')
            expect(trigger).toContainElement(hdr)
        })

        it('renders body content inside the body element', () => {
            render(
                <ExpandableCard id="x" header="H">
                    <div data-testid="body">body content</div>
                </ExpandableCard>
            )
            const body = screen.getByTestId('body')
            const wrapper = body.parentElement!
            expect(wrapper.classList.contains('expandable-card__body')).toBe(true)
        })
    })

    describe('single-open accordion via controlled mode', () => {
        // Integration-style test: parent owns "which id is open" and
        // passes `isOpen={state === id}` to each child. Clicking one
        // closes the previously-open one.
        function AccordionHarness() {
            const [openId, setOpenId] = useState<string | null>(null)
            const cards = ['a', 'b', 'c']
            return (
                <>
                    {cards.map((id) => (
                        <ExpandableCard
                            key={id}
                            id={id}
                            isOpen={openId === id}
                            onToggle={() => setOpenId((prev) => (prev === id ? null : id))}
                            header={`Card ${id}`}
                        >
                            <div data-testid={`body-${id}`}>Body {id}</div>
                        </ExpandableCard>
                    ))}
                </>
            )
        }

        it('opens one card at a time — opening B closes previously-open A', () => {
            render(<AccordionHarness />)
            const triggers = screen.getAllByRole('button')
            fireEvent.click(triggers[0]) // open A
            expect(triggers[0]).toHaveAttribute('aria-expanded', 'true')
            fireEvent.click(triggers[1]) // open B
            expect(triggers[1]).toHaveAttribute('aria-expanded', 'true')
            // A is now closed.
            expect(triggers[0]).toHaveAttribute('aria-expanded', 'false')
        })

        it('clicking the same trigger twice closes it', () => {
            render(<AccordionHarness />)
            const trigger = screen.getAllByRole('button')[0]
            fireEvent.click(trigger)
            expect(trigger).toHaveAttribute('aria-expanded', 'true')
            fireEvent.click(trigger)
            expect(trigger).toHaveAttribute('aria-expanded', 'false')
        })
    })
})
