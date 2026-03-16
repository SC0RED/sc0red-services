import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import DocumentUpload from '@/components/DocumentUpload'
import type { DocumentInfo } from '@/lib/types/api'

const mockFetch = vi.fn()
global.fetch = mockFetch

/** Create a File with a working arrayBuffer() method (JSDOM doesn't support it natively). */
function createFile(content: string, name: string, type: string): File {
    const file = new File([content], name, { type })
    file.arrayBuffer = () => Promise.resolve(new TextEncoder().encode(content).buffer)
    return file
}

function buildDocument(overrides: Partial<DocumentInfo> = {}): DocumentInfo {
    return {
        id: 'doc-1',
        filename: 'report.pdf',
        fileType: 'pdf',
        charCount: 5000,
        uploadedAt: '2026-03-10T00:00:00Z',
        ...overrides,
    }
}

describe('DocumentUpload', () => {
    const defaultProps = {
        analysisId: 'analysis-1',
        documents: [] as DocumentInfo[],
        onDocumentsChange: vi.fn(),
        onReanalyze: vi.fn(),
        reanalyzing: false,
    }

    beforeEach(() => {
        vi.clearAllMocks()
        mockFetch.mockReset()
    })

    it('renders drop zone with upload instructions', () => {
        render(<DocumentUpload {...defaultProps} />)

        expect(screen.getByText('Documents')).toBeInTheDocument()
        expect(screen.getByText('Drop a file here or click to browse')).toBeInTheDocument()
        expect(screen.getByText(/PDF, DOCX, XLSX, TXT, CSV, MD/)).toBeInTheDocument()
    })

    it('renders document list when documents exist', () => {
        const documents = [
            buildDocument({ id: 'doc-1', filename: 'report.pdf', charCount: 5000 }),
            buildDocument({ id: 'doc-2', filename: 'memo.docx', charCount: 12500 }),
        ]
        render(<DocumentUpload {...defaultProps} documents={documents} />)

        expect(screen.getByText('report.pdf')).toBeInTheDocument()
        expect(screen.getByText('5.0K chars')).toBeInTheDocument()
        expect(screen.getByText('memo.docx')).toBeInTheDocument()
        expect(screen.getByText('12.5K chars')).toBeInTheDocument()
    })

    it('shows re-analyze button when documents exist and onReanalyze provided', () => {
        const documents = [buildDocument()]
        render(<DocumentUpload {...defaultProps} documents={documents} />)

        expect(screen.getByText('Re-analyze with Documents')).toBeInTheDocument()
    })

    it('hides re-analyze button when no documents', () => {
        render(<DocumentUpload {...defaultProps} />)

        expect(screen.queryByText('Re-analyze with Documents')).not.toBeInTheDocument()
    })

    it('hides re-analyze button when onReanalyze not provided', () => {
        const documents = [buildDocument()]
        render(<DocumentUpload analysisId="analysis-1" documents={documents} onDocumentsChange={vi.fn()} />)

        expect(screen.queryByText('Re-analyze with Documents')).not.toBeInTheDocument()
    })

    it('shows re-analyzing state when reanalyzing is true', () => {
        const documents = [buildDocument()]
        render(<DocumentUpload {...defaultProps} documents={documents} reanalyzing={true} />)

        const button = screen.getByText('Re-analyzing...')
        expect(button).toBeInTheDocument()
        expect(button).toBeDisabled()
    })

    it('calls onReanalyze when re-analyze button is clicked', () => {
        const documents = [buildDocument()]
        render(<DocumentUpload {...defaultProps} documents={documents} />)

        fireEvent.click(screen.getByText('Re-analyze with Documents'))
        expect(defaultProps.onReanalyze).toHaveBeenCalledOnce()
    })

    it('uploads file via S3 presigned URL when available', async () => {
        // 1. upload-url returns presigned URL
        mockFetch.mockResolvedValueOnce({
            ok: true,
            json: () =>
                Promise.resolve({
                    uploadUrl: 'https://s3.example.com/presigned',
                    documentKey: 'uploads/analysis-1/abc.txt',
                }),
        })
        // 2. PUT to presigned URL succeeds
        mockFetch.mockResolvedValueOnce({ ok: true })
        // 3. POST to /documents succeeds
        mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) })

        render(<DocumentUpload {...defaultProps} />)

        const file = createFile('hello world', 'test.txt', 'text/plain')
        const input = document.querySelector('input[type="file"]') as HTMLInputElement
        fireEvent.change(input, { target: { files: [file] } })

        await waitFor(() => {
            // Should have called upload-url, then PUT, then register document
            expect(mockFetch).toHaveBeenCalledTimes(3)
        })

        // Verify upload-url call
        expect(mockFetch).toHaveBeenNthCalledWith(
            1,
            '/api/analysis/analysis-1/upload-url',
            expect.objectContaining({ method: 'POST' })
        )
        // Verify PUT to presigned URL
        expect(mockFetch).toHaveBeenNthCalledWith(
            2,
            'https://s3.example.com/presigned',
            expect.objectContaining({ method: 'PUT' })
        )
        // Verify register call includes documentKey
        const registerCall = mockFetch.mock.calls[2]
        const registerBody = JSON.parse(registerCall[1].body as string)
        expect(registerBody.documentKey).toBe('uploads/analysis-1/abc.txt')
        expect(registerBody.fileContent).toBeUndefined()

        expect(defaultProps.onDocumentsChange).toHaveBeenCalled()
    })

    it('falls back to base64 when upload-url returns non-ok', async () => {
        // 1. upload-url returns 501 (S3 not configured)
        mockFetch.mockResolvedValueOnce({ ok: false, status: 501 })
        // 2. POST to /documents succeeds with base64
        mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) })

        render(<DocumentUpload {...defaultProps} />)

        const file = createFile('hello world', 'test.txt', 'text/plain')
        const input = document.querySelector('input[type="file"]') as HTMLInputElement
        fireEvent.change(input, { target: { files: [file] } })

        await waitFor(() => {
            expect(mockFetch).toHaveBeenCalledTimes(2)
        })

        // Verify register call includes fileContent (base64), not documentKey
        const registerCall = mockFetch.mock.calls[1]
        const registerBody = JSON.parse(registerCall[1].body as string)
        expect(registerBody.fileContent).toBeDefined()
        expect(registerBody.documentKey).toBeUndefined()

        expect(defaultProps.onDocumentsChange).toHaveBeenCalled()
    })

    it('shows error for unsupported file type', async () => {
        render(<DocumentUpload {...defaultProps} />)

        const file = new File(['data'], 'image.png', { type: 'image/png' })
        const input = document.querySelector('input[type="file"]') as HTMLInputElement
        fireEvent.change(input, { target: { files: [file] } })

        await waitFor(() => {
            expect(screen.getByText('Unsupported file type: .png')).toBeInTheDocument()
        })

        expect(mockFetch).not.toHaveBeenCalled()
    })

    it('shows error for file too large', async () => {
        render(<DocumentUpload {...defaultProps} />)

        // Create a file > 10 MB
        const largeContent = new ArrayBuffer(11 * 1024 * 1024)
        const file = new File([largeContent], 'big.pdf', { type: 'application/pdf' })
        const input = document.querySelector('input[type="file"]') as HTMLInputElement
        fireEvent.change(input, { target: { files: [file] } })

        await waitFor(() => {
            expect(screen.getByText('File too large (max 10 MB)')).toBeInTheDocument()
        })

        expect(mockFetch).not.toHaveBeenCalled()
    })

    it('shows error when upload fails', async () => {
        // upload-url fails (no S3)
        mockFetch.mockResolvedValueOnce({ ok: false, status: 501 })
        // document registration also fails
        mockFetch.mockResolvedValueOnce({
            ok: false,
            json: () => Promise.resolve({ error: 'Bad request' }),
        })

        render(<DocumentUpload {...defaultProps} />)

        const file = createFile('data', 'test.csv', 'text/csv')
        const input = document.querySelector('input[type="file"]') as HTMLInputElement
        fireEvent.change(input, { target: { files: [file] } })

        await waitFor(() => {
            expect(screen.getByText('Bad request')).toBeInTheDocument()
        })
    })

    it('deletes document and calls onDocumentsChange', async () => {
        mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) })

        const documents = [buildDocument()]
        render(<DocumentUpload {...defaultProps} documents={documents} />)

        fireEvent.click(screen.getByText('Remove'))

        await waitFor(() => {
            expect(mockFetch).toHaveBeenCalledWith('/api/analysis/analysis-1/documents/doc-1', {
                method: 'DELETE',
            })
        })

        expect(defaultProps.onDocumentsChange).toHaveBeenCalled()
    })

    it('shows error when delete fails', async () => {
        mockFetch.mockResolvedValueOnce({ ok: false })

        const documents = [buildDocument()]
        render(<DocumentUpload {...defaultProps} documents={documents} />)

        fireEvent.click(screen.getByText('Remove'))

        await waitFor(() => {
            expect(screen.getByText('Failed to delete document')).toBeInTheDocument()
        })
    })

    it('handles drag and drop upload', async () => {
        // upload-url fails (S3 not configured), then document register succeeds
        mockFetch.mockResolvedValueOnce({ ok: false, status: 501 })
        mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) })

        render(<DocumentUpload {...defaultProps} />)

        const dropZone = screen.getByTestId('drop-zone')
        const file = createFile('content', 'notes.md', 'text/markdown')

        fireEvent.dragOver(dropZone)
        fireEvent.drop(dropZone, { dataTransfer: { files: [file] } })

        await waitFor(() => {
            expect(mockFetch).toHaveBeenCalledWith(
                '/api/analysis/analysis-1/documents',
                expect.objectContaining({ method: 'POST' })
            )
        })
    })

    it('formats char count below 1000 without K suffix', () => {
        const documents = [buildDocument({ charCount: 500 })]
        render(<DocumentUpload {...defaultProps} documents={documents} />)

        expect(screen.getByText('500 chars')).toBeInTheDocument()
    })
})
