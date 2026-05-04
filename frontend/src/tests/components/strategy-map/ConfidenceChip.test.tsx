import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import ConfidenceChip from '@/components/strategy-map/ConfidenceChip'

describe('ConfidenceChip', () => {
    it.each(['HIGH', 'MEDIUM', 'LOW'] as const)('renders the %s marker', (level) => {
        render(<ConfidenceChip confidence={level} />)
        expect(screen.getByText(level)).toBeInTheDocument()
    })

    it('exposes a tooltip via the title attribute', () => {
        const { container } = render(<ConfidenceChip confidence="LOW" />)
        const chip = container.firstElementChild as HTMLElement | null
        expect(chip?.title).toContain('Inferred from absence')
    })
})
