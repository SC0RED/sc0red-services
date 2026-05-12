import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import WhatsMissingPanel from '@/components/strategy-map/WhatsMissingPanel'
import type { Gap } from '@/lib/types/api'

const gaps: Gap[] = [
    {
        id: 'G1',
        title: 'Cultural commitments not published',
        description: 'Public materials reference associate ownership but do not articulate specific values.',
        deepDiveFraming: 'A Vector Advisory deep-dive would interview leadership and frontline associates.',
        relatedObjectiveIds: ['O.C'],
    },
    {
        id: 'G2',
        title: 'Channel-relationship strategy unclear',
        description: 'The company sells through multiple channels but the balance is not visible.',
        deepDiveFraming: 'A Vector Advisory deep-dive would map the channel economics.',
    },
]

describe('WhatsMissingPanel — base rendering', () => {
    it('returns null when no gaps are provided', () => {
        const { container } = render(<WhatsMissingPanel gaps={[]} />)
        expect(container.firstChild).toBeNull()
    })

    it('renders the panel header and every gap title', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        expect(screen.getByTestId('strategy-map-whats-missing')).toBeInTheDocument()
        expect(screen.getByText('Cultural commitments not published')).toBeInTheDocument()
        expect(screen.getByText('Channel-relationship strategy unclear')).toBeInTheDocument()
    })

    it('renders each gap ID as a monospaced prefix', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        expect(screen.getByText('G1')).toBeInTheDocument()
        expect(screen.getByText('G2')).toBeInTheDocument()
    })
})

describe('WhatsMissingPanel — accordion behaviour', () => {
    it('hides every gap description by default', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        expect(screen.queryByText(gaps[0].description)).toBeNull()
        expect(screen.queryByText(gaps[1].description)).toBeNull()
        expect(screen.queryByText(gaps[0].deepDiveFraming)).toBeNull()
        expect(screen.queryByText(gaps[1].deepDiveFraming)).toBeNull()
    })

    it('marks every gap row with aria-expanded=false initially', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        const buttons = screen.getAllByRole('button')
        expect(buttons).toHaveLength(2)
        for (const button of buttons) {
            expect(button).toHaveAttribute('aria-expanded', 'false')
        }
    })

    it('expands a gap row inline when its toggle is clicked', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        const firstButton = screen.getAllByRole('button')[0]
        fireEvent.click(firstButton)

        expect(firstButton).toHaveAttribute('aria-expanded', 'true')
        expect(screen.getByText(gaps[0].description)).toBeInTheDocument()
        expect(screen.getByText(gaps[0].deepDiveFraming)).toBeInTheDocument()
        // Second row stays closed.
        expect(screen.queryByText(gaps[1].description)).toBeNull()
    })

    it('collapses the previously open gap when another gap is clicked (single-open)', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        const [firstButton, secondButton] = screen.getAllByRole('button')

        fireEvent.click(firstButton)
        expect(firstButton).toHaveAttribute('aria-expanded', 'true')

        fireEvent.click(secondButton)
        expect(firstButton).toHaveAttribute('aria-expanded', 'false')
        expect(secondButton).toHaveAttribute('aria-expanded', 'true')

        // First gap's content gone, second's content visible.
        expect(screen.queryByText(gaps[0].description)).toBeNull()
        expect(screen.getByText(gaps[1].description)).toBeInTheDocument()
    })

    it('collapses an open gap when its own toggle is clicked again', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        const firstButton = screen.getAllByRole('button')[0]
        fireEvent.click(firstButton)
        expect(firstButton).toHaveAttribute('aria-expanded', 'true')

        fireEvent.click(firstButton)
        expect(firstButton).toHaveAttribute('aria-expanded', 'false')
        expect(screen.queryByText(gaps[0].description)).toBeNull()
    })

    it('uses aria-controls pointing at the gap detail region', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        const firstButton = screen.getAllByRole('button')[0]
        const controls = firstButton.getAttribute('aria-controls')
        expect(controls).toBe('whats-missing-detail-G1')

        fireEvent.click(firstButton)
        const detail = document.getElementById('whats-missing-detail-G1')
        expect(detail).not.toBeNull()
    })
})
