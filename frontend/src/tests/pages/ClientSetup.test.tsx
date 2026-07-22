import { screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import { renderWithProviders as render } from '@/tests/test-utils'

import ClientSetup from '@/app/(authenticated)/settings/connect/ClientSetup'

const URL = 'https://mcp.prod.services.sc0red.ai/mcp'

describe('ClientSetup', () => {
    beforeEach(() => vi.clearAllMocks())

    it('defaults to the Claude Desktop tab and can switch tabs', () => {
        render(<ClientSetup url={URL} available />)
        expect(screen.getByText(/Add custom connector/i)).toBeInTheDocument()
        fireEvent.click(screen.getByRole('tab', { name: 'Cursor & others' }))
        expect(screen.getByText(/the first time Cursor connects/i)).toBeInTheDocument()
    })

    it('embeds the server address in the Cursor snippet', () => {
        render(<ClientSetup url={URL} available />)
        fireEvent.click(screen.getByRole('tab', { name: 'Cursor & others' }))
        expect(screen.getByText(new RegExp(URL.replace(/[.]/g, '\\.')))).toBeInTheDocument()
    })

    it('ChatGPT tab is a hedged pointer that links to OpenAI, not a walkthrough', () => {
        render(<ClientSetup url={URL} available />)
        fireEvent.click(screen.getByRole('tab', { name: 'ChatGPT' }))
        expect(screen.getByText(/beta/i)).toBeInTheDocument()
        const link = screen.getByRole('link', { name: /Developer Mode guide/i })
        expect(link).toHaveAttribute('href', expect.stringContaining('help.openai.com'))
    })

    it('hides URL-dependent snippets when the address is unavailable', () => {
        render(<ClientSetup url="" available={false} />)
        fireEvent.click(screen.getByRole('tab', { name: 'Cursor & others' }))
        expect(screen.queryByText(/"url"/)).not.toBeInTheDocument()
        expect(screen.getByText(/will appear here once the server address is available/i)).toBeInTheDocument()
    })
})
