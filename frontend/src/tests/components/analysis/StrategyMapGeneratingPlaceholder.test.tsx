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

    it('falls back to the static spinner when no progress is reported', () => {
        // ``progress=null`` is the default and the cold-load shape: no
        // AppSync events have arrived yet (or AppSync is unconfigured).
        // The placeholder must still render its full body.
        render(<StrategyMapGeneratingPlaceholder progress={null} />)

        expect(screen.queryByRole('progressbar')).toBeNull()
        expect(screen.getByText('Generating your strategy map…')).toBeInTheDocument()
    })

    it('renders a progress bar with worker-supplied label when progress arrives', () => {
        render(
            <StrategyMapGeneratingPlaceholder
                progress={{ percentage: 42, label: 'Mapping internal processes…' }}
            />
        )

        const bar = screen.getByRole('progressbar', {
            name: /Strategy map generation progress/i,
        })
        expect(bar).toHaveAttribute('aria-valuenow', '42')
        expect(bar).toHaveAttribute('aria-valuemin', '0')
        expect(bar).toHaveAttribute('aria-valuemax', '100')

        // Worker-supplied label replaces the default spinner copy.
        expect(screen.getByText('Mapping internal processes…')).toBeInTheDocument()
        expect(screen.queryByText('Generating your strategy map…')).toBeNull()
    })

    it('clamps percentage values outside 0-100 in both width and aria-valuenow', () => {
        // Defensive: a malformed worker event with `progress: 150` (or
        // `-5`) shouldn't render an oversized bar OR a screen-reader
        // announcement of "150 out of 100" (ARIA spec requires
        // valuemin <= valuenow <= valuemax). Clamp BOTH the fill width
        // and aria-valuenow.
        const { rerender } = render(
            <StrategyMapGeneratingPlaceholder progress={{ percentage: 150, label: 'overshoot' }} />
        )
        const bar = screen.getByRole('progressbar')
        const fill = bar.firstChild as HTMLElement
        expect(fill.style.width).toBe('100%')
        expect(bar).toHaveAttribute('aria-valuenow', '100')

        rerender(<StrategyMapGeneratingPlaceholder progress={{ percentage: -10, label: 'undershoot' }} />)
        const negativeBar = screen.getByRole('progressbar')
        const negativeFill = negativeBar.firstChild as HTMLElement
        expect(negativeFill.style.width).toBe('0%')
        expect(negativeBar).toHaveAttribute('aria-valuenow', '0')
    })
})
