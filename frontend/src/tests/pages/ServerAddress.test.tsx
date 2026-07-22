import { screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

import ServerAddress from '@/app/(authenticated)/settings/connect/ServerAddress'

const URL = 'https://mcp.prod.services.sc0red.ai/mcp'

describe('ServerAddress', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
    })

    it('shows the address and copies the exact URL to the clipboard', async () => {
        render(<ServerAddress url={URL} available />)
        expect(screen.getByTestId('mcp-server-address')).toHaveTextContent(URL)
        fireEvent.click(screen.getByLabelText('Copy server address'))
        expect(navigator.clipboard.writeText).toHaveBeenCalledWith(URL)
        await waitFor(() => expect(screen.getByLabelText('Copy server address')).toHaveTextContent('Copied'))
    })

    it('renders the unavailable state (no address, no copy) when not available', () => {
        render(<ServerAddress url="" available={false} />)
        expect(screen.getByTestId('mcp-address-unavailable')).toBeInTheDocument()
        expect(screen.queryByTestId('mcp-server-address')).not.toBeInTheDocument()
        expect(screen.queryByLabelText('Copy server address')).not.toBeInTheDocument()
    })
})
