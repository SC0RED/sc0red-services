import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import StrategyMapGeneratingPlaceholder from '@/components/analysis/StrategyMapGeneratingPlaceholder'

/**
 * Skeleton + status block rendered while the on-demand strategy-map
 * worker is in flight. Per the strategy-map-on-demand spec the slot is
 * NOT cancellable — the test confirms no cancel control is rendered, so
 * a future refactor that adds one would need to revisit the spec
 * decision (the worker isn't reliably interruptible).
 */
describe('StrategyMapGeneratingPlaceholder', () => {
    it('renders the live-region status copy and stable testid', () => {
        render(<StrategyMapGeneratingPlaceholder />)

        const wrapper = screen.getByTestId('strategy-map-generating')
        expect(wrapper).toBeInTheDocument()
        expect(screen.getByText(/Generating your strategy map/i)).toBeInTheDocument()
        expect(screen.getByText(/usually takes under a minute/i)).toBeInTheDocument()
    })

    it('does NOT render a cancel control', () => {
        render(<StrategyMapGeneratingPlaceholder />)

        // No interactive control — the worker isn't interruptible.
        expect(screen.queryByRole('button')).toBeNull()
    })
})
