import { screen, fireEvent, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

import ConnectView from '@/app/(authenticated)/connect/ConnectView'

const URL = 'https://mcp.prod.services.sc0red.ai/mcp'
// Names deliberately avoid the tab labels (Claude Desktop / Cursor) so getByText
// isn't ambiguous between a connected-app row and a setup tab.
const mockApps = [
    { client_id: 'c1', client_name: 'MCP Inspector', consented_at: 1717000000 },
    { client_id: 'c2', client_name: 'My Assistant', consented_at: null },
]

describe('ConnectView', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        global.fetch = vi.fn().mockResolvedValue({ ok: true })
    })

    it('shows the server address and the setup + connected sections', () => {
        render(<ConnectView mcpServerUrl={URL} initialApps={mockApps} />)
        expect(screen.getByTestId('mcp-server-address')).toHaveTextContent(URL)
        expect(screen.getByRole('heading', { name: /set it up in your assistant/i })).toBeInTheDocument()
        expect(screen.getByText('MCP Inspector')).toBeInTheDocument()
        expect(screen.getByText('My Assistant')).toBeInTheDocument()
    })

    it('renders the unavailable state when the address is missing/invalid', () => {
        render(<ConnectView mcpServerUrl="" initialApps={[]} />)
        expect(screen.getByTestId('mcp-address-unavailable')).toBeInTheDocument()
        expect(screen.queryByTestId('mcp-server-address')).not.toBeInTheDocument()
    })

    it('shows an empty connected state that points at the steps above', () => {
        render(<ConnectView mcpServerUrl={URL} initialApps={[]} />)
        expect(screen.getByText(/Nothing connected yet/i)).toBeInTheDocument()
    })

    describe('disconnect (toast.undo)', () => {
        beforeEach(() => vi.useFakeTimers())
        afterEach(() => vi.useRealTimers())

        it('removes the row immediately and DELETEs after the undo window', async () => {
            render(<ConnectView mcpServerUrl={URL} initialApps={mockApps} />)
            fireEvent.click(screen.getByLabelText('Disconnect MCP Inspector'))
            expect(screen.queryByText('MCP Inspector')).not.toBeInTheDocument()
            expect(global.fetch).not.toHaveBeenCalled()
            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })
            expect(global.fetch).toHaveBeenCalledWith('/api/connected-apps/c1', { method: 'DELETE' })
        })

        it('clicking Undo restores the row and skips the DELETE', () => {
            render(<ConnectView mcpServerUrl={URL} initialApps={mockApps} />)
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
            render(<ConnectView mcpServerUrl={URL} initialApps={mockApps} />)
            fireEvent.click(screen.getByLabelText('Disconnect MCP Inspector'))
            expect(screen.queryByText('MCP Inspector')).not.toBeInTheDocument()
            await act(async () => {
                await vi.advanceTimersByTimeAsync(5000)
            })
            expect(screen.getByText('MCP Inspector')).toBeInTheDocument()
        })
    })
})
