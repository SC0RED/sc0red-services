import { render, screen } from '@testing-library/react'
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

describe('WhatsMissingPanel', () => {
    it('returns null when no gaps are provided', () => {
        const { container } = render(<WhatsMissingPanel gaps={[]} />)
        expect(container.firstChild).toBeNull()
    })

    it('renders the panel header and each gap', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        expect(screen.getByTestId('strategy-map-whats-missing')).toBeInTheDocument()
        expect(screen.getByText('Cultural commitments not published')).toBeInTheDocument()
        expect(screen.getByText('Channel-relationship strategy unclear')).toBeInTheDocument()
    })

    it("renders each gap's description and deep-dive framing", () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        for (const gap of gaps) {
            expect(screen.getByText(gap.description)).toBeInTheDocument()
            expect(screen.getByText(gap.deepDiveFraming)).toBeInTheDocument()
        }
    })

    it('renders the gap IDs as monospaced prefixes', () => {
        render(<WhatsMissingPanel gaps={gaps} />)
        expect(screen.getByText('G1')).toBeInTheDocument()
        expect(screen.getByText('G2')).toBeInTheDocument()
    })
})
