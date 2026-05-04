import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import ObjectiveCard from '@/components/strategy-map/ObjectiveCard'

describe('ObjectiveCard', () => {
    it('renders the ID prefix, title, definition, and confidence chip', () => {
        render(
            <ObjectiveCard
                id="F1"
                title="Grow profitable revenue"
                definition="We will grow revenue by deepening engagement with current customers."
                confidence="HIGH"
            />
        )
        expect(screen.getByText('F1')).toBeInTheDocument()
        expect(screen.getByText('Grow profitable revenue')).toBeInTheDocument()
        expect(screen.getByText(/We will grow revenue by deepening engagement/)).toBeInTheDocument()
        expect(screen.getByText('HIGH')).toBeInTheDocument()
    })

    it('wraps the title in quotation marks when customerVoice is set', () => {
        render(
            <ObjectiveCard
                id="C1"
                title="Offer me fresh products"
                definition="I rely on this brand for fast service."
                confidence="HIGH"
                customerVoice
            />
        )
        expect(screen.getByText('"Offer me fresh products"')).toBeInTheDocument()
        // The plain (un-quoted) title should NOT appear when customerVoice is on.
        expect(screen.queryByText('Offer me fresh products')).not.toBeInTheDocument()
    })

    it('does not wrap the title when customerVoice is omitted', () => {
        render(<ObjectiveCard id="F1" title="Grow profitable revenue" definition="def" confidence="MEDIUM" />)
        expect(screen.getByText('Grow profitable revenue')).toBeInTheDocument()
        expect(screen.queryByText('"Grow profitable revenue"')).not.toBeInTheDocument()
    })
})
