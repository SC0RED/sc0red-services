import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import AnalysisSection from '@/components/analysis/AnalysisSection'

/**
 * Coverage focus: the wrapper is purely presentational. The
 * contracts that downstream consumers (and the spec) depend on:
 *   - `data-testid="analysis-section-{id}"` is ALWAYS emitted,
 *     regardless of title/lead/titleAdornment presence — so order
 *     tests work even for body-only sections like AnalysisHeader.
 *   - Title renders as `<h2 className="section-header">` when
 *     provided, and not at all when undefined (no empty `<h2>`).
 *   - Title accepts ReactNode for non-interactive inline content
 *     (e.g. count badge text). For INTERACTIVE content like
 *     `<HelpTooltip>`, callers should use `titleAdornment` instead
 *     — the adornment slot renders as a sibling of the `<h2>` so
 *     the heading's accessible name stays clean and the adornment
 *     is independently focusable.
 *   - Lead renders as a `<p>` below the title and above the body.
 *   - Children always render inside the wrapper.
 *
 * No state, no hooks, no side effects to exercise.
 */

describe('AnalysisSection', () => {
    it('emits the testid attribute on the wrapper element', () => {
        render(
            <AnalysisSection id="ebitda">
                <div>body</div>
            </AnalysisSection>
        )
        expect(screen.getByTestId('analysis-section-ebitda')).toBeInTheDocument()
    })

    it('renders only the wrapper + children when no title or lead', () => {
        const { container } = render(
            <AnalysisSection id="header">
                <span>just-body</span>
            </AnalysisSection>
        )
        // No <h2>, no <p> at the top level — body-only section.
        expect(container.querySelector('h2')).toBeNull()
        expect(container.querySelector('p')).toBeNull()
        expect(screen.getByText('just-body')).toBeInTheDocument()
    })

    it('renders a string title as <h2 className="section-header">', () => {
        render(
            <AnalysisSection id="risk-breakdown" title="Risk Breakdown">
                <div>body</div>
            </AnalysisSection>
        )
        const heading = screen.getByRole('heading', { level: 2, name: 'Risk Breakdown' })
        expect(heading).toBeInTheDocument()
        expect(heading.classList.contains('section-header')).toBe(true)
    })

    it('renders a ReactNode title with non-interactive inline content inside the h2', () => {
        // The `title` prop accepts ReactNode so callers can include
        // structural inline content like a count badge (e.g.
        // "AI Opportunities (3)" composed as a fragment) inside the
        // heading text. This test pins that capability.
        //
        // NOTE: this is the path for NON-INTERACTIVE content only.
        // Interactive content like `<HelpTooltip>` must NOT go inside
        // `title` — use the `titleAdornment` slot below so the
        // adornment renders as a sibling of the <h2>. See the
        // titleAdornment tests later in this file.
        const Badge = () => <span data-testid="badge">help</span>
        render(
            <AnalysisSection
                id="ebitda"
                title={
                    <>
                        EBITDA Impact Model
                        <Badge />
                    </>
                }
            >
                <div>body</div>
            </AnalysisSection>
        )
        const heading = screen.getByRole('heading', { level: 2 })
        expect(heading).toHaveTextContent('EBITDA Impact Model')
        const badge = screen.getByTestId('badge')
        expect(heading).toContainElement(badge)
    })

    it('renders the lead paragraph between the title and the children', () => {
        const { container } = render(
            <AnalysisSection
                id="document-upload"
                title="Improve This Analysis"
                lead="Upload financial statements to refine this analysis."
            >
                <div data-testid="body">body</div>
            </AnalysisSection>
        )
        const lead = container.querySelector('p')
        expect(lead).not.toBeNull()
        expect(lead).toHaveTextContent('Upload financial statements to refine this analysis.')
        // Lead carries the canonical `.section-lead` class, NOT inline
        // styles — same DRY pattern as `.section-header` (D4 + review fix).
        expect(lead!.classList.contains('section-lead')).toBe(true)
        // Order: heading → lead → body
        const heading = screen.getByRole('heading', { level: 2 })
        const body = screen.getByTestId('body')
        const headingPos = heading.compareDocumentPosition(lead!)
        const leadPos = lead!.compareDocumentPosition(body)
        // DOCUMENT_POSITION_FOLLOWING (4) → lead follows heading
        expect(headingPos & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
        // body follows lead
        expect(leadPos & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })

    it('does NOT render an empty <h2> when title is explicitly null', () => {
        // Defensive contract: ReactNode permits null. A caller passing
        // `title={null}` (e.g., a conditional like `title={x ?? null}`)
        // must not render an empty heading. This locks the `!= null`
        // check against a regression to `!== undefined`.
        const { container } = render(
            <AnalysisSection id="x" title={null}>
                <div>body</div>
            </AnalysisSection>
        )
        expect(container.querySelector('h2')).toBeNull()
    })

    it('does NOT render an empty <p> when lead is explicitly null', () => {
        const { container } = render(
            <AnalysisSection id="x" lead={null}>
                <div>body</div>
            </AnalysisSection>
        )
        expect(container.querySelector('p')).toBeNull()
    })

    it('renders the lead even when no title is provided', () => {
        // Edge case — uncommon but the prop contract allows it.
        // Verify the component doesn't crash and the lead still renders.
        const { container } = render(
            <AnalysisSection id="x" lead="Lead-only section">
                <div>body</div>
            </AnalysisSection>
        )
        expect(container.querySelector('h2')).toBeNull()
        expect(container.querySelector('p')).toHaveTextContent('Lead-only section')
    })

    it('always emits the testid regardless of title/lead presence', () => {
        // Three call shapes, one assertion each — proves the
        // unconditional testid contract that the order-tests rely on.
        const { rerender } = render(
            <AnalysisSection id="x">
                <div>body</div>
            </AnalysisSection>
        )
        expect(screen.getByTestId('analysis-section-x')).toBeInTheDocument()

        rerender(
            <AnalysisSection id="x" title="t">
                <div>body</div>
            </AnalysisSection>
        )
        expect(screen.getByTestId('analysis-section-x')).toBeInTheDocument()

        rerender(
            <AnalysisSection id="x" title="t" lead="l">
                <div>body</div>
            </AnalysisSection>
        )
        expect(screen.getByTestId('analysis-section-x')).toBeInTheDocument()
    })

    // ── titleAdornment slot (extract-definition-popover) ─────────────────

    it('renders a titleAdornment as a sibling of the h2, NOT inside it', () => {
        // The structural fix: the adornment must NOT be a descendant of
        // the heading element. This is the regression guard for the
        // accessible-name run-on bug — when an adornment lived inside
        // the <h2>, screen readers concatenated its aria-label into the
        // heading's accessible name.
        render(
            <AnalysisSection
                id="ebitda"
                title="EBITDA Impact Model"
                titleAdornment={<button data-testid="adorn">help</button>}
            >
                <div>body</div>
            </AnalysisSection>
        )
        const heading = screen.getByRole('heading', { level: 2, name: 'EBITDA Impact Model' })
        const adornment = screen.getByTestId('adorn')
        // Adornment is rendered, but NOT inside the heading.
        expect(adornment).toBeInTheDocument()
        expect(heading.contains(adornment)).toBe(false)
    })

    it('keeps the h2 accessible name exactly the title text when an adornment is present', () => {
        render(
            <AnalysisSection
                id="ebitda"
                title="EBITDA Impact Model"
                titleAdornment={<button aria-label="What is EBITDA Tree?">i</button>}
            >
                <div>body</div>
            </AnalysisSection>
        )
        // Exact-match heading query. Note: this is a REGRESSION GUARD,
        // not the structural proof — `dom-accessibility-api` (used by
        // testing-library) does not concatenate a descendant button's
        // `aria-label` into the parent heading's computed name when the
        // button's visible content is `aria-hidden` (which HelpTooltip
        // does on its SVG). The TRUE structural proof that the button
        // is NOT a descendant of the heading is the
        // `heading.contains(adornment)).toBe(false)` assertion in the
        // sibling-not-child test above. The exact-match query stays as
        // a guard against future visual regressions where someone
        // smuggles raw text into the title prop.
        expect(screen.getByRole('heading', { level: 2, name: 'EBITDA Impact Model' })).toBeInTheDocument()
    })

    it('places title and adornment inside a .section-header-row container', () => {
        const { container } = render(
            <AnalysisSection id="x" title="Section Title" titleAdornment={<span data-testid="adorn">!</span>}>
                <div>body</div>
            </AnalysisSection>
        )
        const row = container.querySelector('.section-header-row')
        expect(row).not.toBeNull()
        // Both heading and adornment live inside the row container.
        expect(row).toContainElement(screen.getByRole('heading', { level: 2 }))
        expect(row).toContainElement(screen.getByTestId('adorn'))
    })

    it('renders adornment-only (no title) without crashing or producing an empty h2', () => {
        // Edge case — uncommon but the prop contract allows it (ReactNode
        // is independently optional for both). No <h2>, but the row
        // wrapper still renders so the adornment has its layout context.
        const { container } = render(
            <AnalysisSection id="x" titleAdornment={<span data-testid="adorn">!</span>}>
                <div>body</div>
            </AnalysisSection>
        )
        expect(container.querySelector('h2')).toBeNull()
        expect(screen.getByTestId('adorn')).toBeInTheDocument()
        expect(container.querySelector('.section-header-row')).not.toBeNull()
    })
})
