import { act, render, screen, fireEvent, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import StrategyMapCTA from '@/components/analysis/StrategyMapCTA'

/**
 * Covers the user-facing interactions on the on-demand "Generate
 * strategy map" button rendered when the strategy-map slot is in the
 * absent state (per the strategy-map-on-demand spec scenario "User
 * clicking the CTA transitions to generating state").
 */
describe('StrategyMapCTA', () => {
    beforeEach(() => {
        global.fetch = vi.fn()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('renders the framing copy and the action button', () => {
        render(<StrategyMapCTA analysisId="a-1" onGenerationStarted={vi.fn()} />)

        expect(screen.getByText('Strategy map')).toBeInTheDocument()
        expect(screen.getByText(/Synthesise a Balanced Scorecard view/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Generate strategy map' })).toBeEnabled()
    })

    it('POSTs to /api/analysis/{id}/strategy-map and fires onGenerationStarted on 202', async () => {
        const fetchMock = vi.fn().mockResolvedValue({
            status: 202,
            json: () => Promise.resolve({ status: 'queued', analysisId: 'a-1' }),
        })
        global.fetch = fetchMock
        const onGenerationStarted = vi.fn()

        render(<StrategyMapCTA analysisId="a-1" onGenerationStarted={onGenerationStarted} />)

        fireEvent.click(screen.getByRole('button', { name: 'Generate strategy map' }))

        await waitFor(() => {
            expect(onGenerationStarted).toHaveBeenCalledTimes(1)
        })
        expect(fetchMock).toHaveBeenCalledWith('/api/analysis/a-1/strategy-map', {
            method: 'POST',
        })
    })

    it('renders the backend error message when the API returns non-202', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            status: 503,
            json: () => Promise.resolve({ error: 'Strategy map generation is unavailable.' }),
        })
        const onGenerationStarted = vi.fn()

        render(<StrategyMapCTA analysisId="a-1" onGenerationStarted={onGenerationStarted} />)

        fireEvent.click(screen.getByRole('button', { name: 'Generate strategy map' }))

        const alert = await screen.findByRole('alert')
        expect(alert).toHaveTextContent('Strategy map generation is unavailable.')
        expect(onGenerationStarted).not.toHaveBeenCalled()
        // Button must be re-enabled so the user can retry.
        expect(screen.getByRole('button', { name: 'Generate strategy map' })).toBeEnabled()
    })

    it('falls back to a generic message when the response body has no error field', async () => {
        global.fetch = vi.fn().mockResolvedValue({
            status: 500,
            json: () => Promise.resolve({}),
        })

        render(<StrategyMapCTA analysisId="a-1" onGenerationStarted={vi.fn()} />)

        fireEvent.click(screen.getByRole('button', { name: 'Generate strategy map' }))

        const alert = await screen.findByRole('alert')
        expect(alert).toHaveTextContent(/Could not start generation/i)
    })

    it('renders a network error when fetch rejects', async () => {
        global.fetch = vi.fn().mockRejectedValue(new Error('Connection refused'))

        render(<StrategyMapCTA analysisId="a-1" onGenerationStarted={vi.fn()} />)

        fireEvent.click(screen.getByRole('button', { name: 'Generate strategy map' }))

        const alert = await screen.findByRole('alert')
        expect(alert).toHaveTextContent(/Network error/i)
    })

    it('renders the parent-supplied failureMessage when no inline error has occurred yet', () => {
        // Used by the parent to surface a prior failed generation when
        // the slot returns to the absent state.
        render(
            <StrategyMapCTA
                analysisId="a-1"
                onGenerationStarted={vi.fn()}
                failureMessage="We couldn't generate your strategy map."
            />
        )

        expect(screen.getByRole('alert')).toHaveTextContent("We couldn't generate your strategy map.")
    })

    it('disables the button + sets aria-busy while the request is in flight', async () => {
        // Resolve the fetch on demand so we can observe the in-flight UI.
        let resolvePost: ((value: unknown) => void) | undefined
        global.fetch = vi.fn().mockImplementation(
            () =>
                new Promise((resolve) => {
                    resolvePost = resolve
                })
        )
        const onGenerationStarted = vi.fn()

        render(<StrategyMapCTA analysisId="a-1" onGenerationStarted={onGenerationStarted} />)

        fireEvent.click(screen.getByRole('button', { name: 'Generate strategy map' }))

        const pendingButton = await screen.findByRole('button', { name: /Starting/i })
        expect(pendingButton).toBeDisabled()
        expect(pendingButton).toHaveAttribute('aria-busy', 'true')

        // Settle the request inside `act` so the post-resolve state
        // updates flush before the test ends. Without this, the
        // `setIsPending(false)` inside the `finally` block would update
        // state outside an `act` boundary and Vitest would warn.
        await act(async () => {
            resolvePost!({
                status: 202,
                json: () => Promise.resolve({ status: 'queued' }),
            })
        })
        await waitFor(() => {
            expect(onGenerationStarted).toHaveBeenCalled()
        })
    })

    it('ignores a second click while the first is still in flight', async () => {
        const fetchMock = vi.fn().mockImplementation(
            () =>
                new Promise(() => {
                    /* never resolves — pending */
                })
        )
        global.fetch = fetchMock

        render(<StrategyMapCTA analysisId="a-1" onGenerationStarted={vi.fn()} />)

        const button = screen.getByRole('button', { name: 'Generate strategy map' })
        fireEvent.click(button)
        fireEvent.click(button)

        // Disabled-button click should be a no-op, but the explicit
        // `isPending` guard is the second line of defence.
        expect(fetchMock).toHaveBeenCalledTimes(1)
    })
})
