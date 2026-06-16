import { screen, fireEvent, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

import ConnectedAppsView from '@/app/(authenticated)/settings/connected-apps/ConnectedAppsView'

const mockApps = [
    { client_id: 'c1', client_name: 'MCP Inspector', consented_at: 1717000000 },
    { client_id: 'c2', client_name: 'Claude Desktop', consented_at: null },
]

describe('ConnectedAppsView', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        global.fetch = vi.fn().mockResolvedValue({ ok: true })
    })

    it('renders the connected apps', () => {
        render(<ConnectedAppsView initialApps={mockApps} />)
        expect(screen.getByText('MCP Inspector')).toBeInTheDocument()
        expect(screen.getByText('Claude Desktop')).toBeInTheDocument()
    })

    it('shows an empty state with connect guidance when there are none', () => {
        render(<ConnectedAppsView initialApps={[]} />)
        expect(screen.getByText(/No connected apps yet/i)).toBeInTheDocument()
        // The "How to connect" guidance section is always present.
        expect(screen.getByRole('heading', { name: /How to connect/i })).toBeInTheDocument()
    })

    describe('disconnect (toast.undo)', () => {
        beforeEach(() => vi.useFakeTimers())
        afterEach(() => vi.useRealTimers())

        it('removes the row immediately and DELETEs after the undo window', async () => {
            render(<ConnectedAppsView initialApps={mockApps} />)
            fireEvent.click(screen.getByLabelText('Disconnect MCP Inspector'))
            // Optimistically removed before the commit window elapses.
            expect(screen.queryByText('MCP Inspector')).not.toBeInTheDocument()
            expect(global.fetch).not.toHaveBeenCalled()
            // The DELETE fires once the 5s undo window commits.
            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })
            expect(global.fetch).toHaveBeenCalledWith('/api/connected-apps/c1', { method: 'DELETE' })
        })

        it('clicking Undo restores the row and skips the DELETE', () => {
            render(<ConnectedAppsView initialApps={mockApps} />)
            fireEvent.click(screen.getByLabelText('Disconnect MCP Inspector'))
            expect(screen.queryByText('MCP Inspector')).not.toBeInTheDocument()

            fireEvent.click(screen.getByText('Undo'))

            expect(screen.getByText('MCP Inspector')).toBeInTheDocument()
            act(() => {
                vi.advanceTimersByTime(10_000)
            })
            expect(global.fetch).not.toHaveBeenCalled()
        })

        it('restores the row when the DELETE fails', async () => {
            global.fetch = vi.fn().mockResolvedValue({ ok: false })
            render(<ConnectedAppsView initialApps={mockApps} />)
            fireEvent.click(screen.getByLabelText('Disconnect MCP Inspector'))
            expect(screen.queryByText('MCP Inspector')).not.toBeInTheDocument()

            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })

            // Row restored after the failed disconnect.
            expect(screen.getByText('MCP Inspector')).toBeInTheDocument()
        })
    })
})
