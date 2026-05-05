import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import AnalysisSection from '@/components/analysis/AnalysisSection'

/**
 * Coverage focus: the wrapper is purely presentational. The
 * contracts that downstream consumers (and the spec) depend on:
 *   - `data-testid="analysis-section-{id}"` is ALWAYS emitted,
 *     regardless of title/lead presence — so order tests work even
 *     for body-only sections like AnalysisHeader.
 *   - Title renders as `<h2 className="section-header">` when
 *     provided, and not at all when undefined (no empty `<h2>`).
 *   - Title accepts ReactNode so adornments (HelpTooltip, count
 *     badges) can sit next to the title text inside the same `<h2>`.
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

    it('renders a ReactNode title with adornments inside the same h2', () => {
        const Adornment = () => <span data-testid="adornment">help</span>
        render(
            <AnalysisSection
                id="ebitda"
                title={
                    <>
                        EBITDA Impact Model
                        <Adornment />
                    </>
                }
            >
                <div>body</div>
            </AnalysisSection>
        )
        // Both the text AND the adornment must live inside the <h2>,
        // not somewhere else in the wrapper. Accessibility tools rely
        // on the heading's accessible name.
        const heading = screen.getByRole('heading', { level: 2 })
        expect(heading).toHaveTextContent('EBITDA Impact Model')
        const adornment = screen.getByTestId('adornment')
        expect(heading).toContainElement(adornment)
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
})
