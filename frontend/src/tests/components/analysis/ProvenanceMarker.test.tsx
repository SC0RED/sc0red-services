import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import ProvenanceMarker from '@/components/analysis/ProvenanceMarker'

/**
 * Coverage focus: ProvenanceMarker's contract.
 *   - Default label per `kind`
 *   - Optional `label` prop overrides the default
 *   - Accessible name is the `kind`-specific phrase ("AI-inferred"),
 *     NOT the visible label or icon path
 *   - Icon is aria-hidden so screen readers don't announce SVG path data
 *   - Renders the `.provenance-marker` class for the centralised CSS
 *     to take effect (regression guard against a contributor inlining
 *     styles like the patterns this component replaces)
 */

describe('ProvenanceMarker', () => {
    it('renders the default "Inferred" label for kind="inferred"', () => {
        render(<ProvenanceMarker kind="inferred" />)
        expect(screen.getByText('Inferred')).toBeInTheDocument()
    })

    it('exposes "AI-inferred" as the accessible name', () => {
        render(<ProvenanceMarker kind="inferred" />)
        expect(screen.getByLabelText('AI-inferred')).toBeInTheDocument()
    })

    it('overrides the visible label when `label` is provided', () => {
        render(<ProvenanceMarker kind="inferred" label="Synthesised" />)
        expect(screen.getByText('Synthesised')).toBeInTheDocument()
        expect(screen.queryByText('Inferred')).toBeNull()
    })

    it('keeps the accessible name stable even when `label` overrides the visible text', () => {
        // The aria-label is per-kind, not derived from the visible
        // label. A caller-overridden visible label shouldn't change
        // what screen readers announce.
        render(<ProvenanceMarker kind="inferred" label="Synthesised" />)
        expect(screen.getByLabelText('AI-inferred')).toBeInTheDocument()
    })

    it('marks the icon as aria-hidden', () => {
        const { container } = render(<ProvenanceMarker kind="inferred" />)
        const icon = container.querySelector('svg')
        expect(icon).not.toBeNull()
        expect(icon!.getAttribute('aria-hidden')).toBe('true')
    })

    it('renders with the centralised .provenance-marker class', () => {
        // Style lives in globals.css. Component just sets the className.
        // Asserting the class is present is the regression guard against
        // a future contributor inlining `style={{...}}` like the
        // patterns this component replaces.
        const { container } = render(<ProvenanceMarker kind="inferred" />)
        const wrapper = container.firstElementChild as HTMLElement
        expect(wrapper.classList.contains('provenance-marker')).toBe(true)
    })

    it('attaches a tooltip explaining the AI-inferred meaning', () => {
        const { container } = render(<ProvenanceMarker kind="inferred" />)
        const wrapper = container.firstElementChild as HTMLElement
        expect(wrapper.title).toMatch(/AI synthesised/i)
    })
})
