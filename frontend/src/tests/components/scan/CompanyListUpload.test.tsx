import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import CompanyListUpload from '@/components/scan/CompanyListUpload'

function makeFile(name: string, content = 'name,url\nAcme,https://acme.com\n'): File {
    const file = new File([content], name, { type: 'text/csv' })
    // jsdom's File does not implement arrayBuffer(); the component needs it
    // to base64-encode the upload.
    Object.defineProperty(file, 'arrayBuffer', {
        value: async () => new TextEncoder().encode(content).buffer,
    })
    return file
}

function selectFile(file: File) {
    const input = screen.getByLabelText('Company list file') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
}

describe('CompanyListUpload', () => {
    beforeEach(() => {
        vi.restoreAllMocks()
    })
    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it('parses a file and reports how many were added', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                ok: true,
                json: async () => ({
                    companies: [
                        { name: 'Acme', url: 'https://acme.com' },
                        { name: 'Beta', url: '' },
                    ],
                    count: 2,
                    withUrl: 1,
                    needsUrl: 1,
                }),
            })
        )
        const onCompaniesParsed = vi.fn(() => 2)
        render(<CompanyListUpload onCompaniesParsed={onCompaniesParsed} />)

        selectFile(makeFile('list.csv'))

        await waitFor(() => expect(onCompaniesParsed).toHaveBeenCalled())
        expect(onCompaniesParsed).toHaveBeenCalledWith([
            { name: 'Acme', url: 'https://acme.com' },
            { name: 'Beta', url: '' },
        ])
        expect(await screen.findByText(/Added 2 companies/)).toBeInTheDocument()
        expect(screen.getByText(/1 need a URL/)).toBeInTheDocument()
    })

    it('rejects an unsupported file type before calling the API', async () => {
        const fetchMock = vi.fn()
        vi.stubGlobal('fetch', fetchMock)
        render(<CompanyListUpload onCompaniesParsed={vi.fn(() => 0)} />)

        selectFile(makeFile('data.exe'))

        expect(await screen.findByRole('alert')).toHaveTextContent('Unsupported file type')
        expect(fetchMock).not.toHaveBeenCalled()
    })

    it('surfaces a backend error message', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn().mockResolvedValue({
                ok: false,
                status: 400,
                json: async () => ({ error: 'No companies found in the uploaded file' }),
            })
        )
        render(<CompanyListUpload onCompaniesParsed={vi.fn(() => 0)} />)

        selectFile(makeFile('empty.csv', '\n\n'))

        expect(await screen.findByRole('alert')).toHaveTextContent('No companies found')
    })
})
