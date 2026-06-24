'use client'

import { useState, useRef, useCallback } from 'react'

interface ParsedCompany {
    name: string
    url: string
}

interface ParseResponse {
    companies: ParsedCompany[]
    count: number
    withUrl: number
    needsUrl: number
}

interface CompanyListUploadProps {
    /** Called with the parsed companies so the parent can merge them into the
     *  editable confirmation list (the parent owns dedup against existing rows).
     *  MUST return the count of companies *actually* added (excluding dedup
     *  hits) — the "Added N" summary is rendered from this value. */
    onCompaniesParsed: (companies: ParsedCompany[]) => number
}

// Spreadsheets are intentionally excluded — the backend rejects xlsx/xls for
// company lists (their extracted text becomes junk candidates); customers
// export those to CSV, which is parsed structurally.
const ALLOWED_TYPES = ['csv', 'pdf', 'docx', 'txt', 'md']
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

async function fileToBase64(file: File): Promise<string> {
    const buffer = await file.arrayBuffer()
    return btoa(new Uint8Array(buffer).reduce((data, byte) => data + String.fromCharCode(byte), ''))
}

export default function CompanyListUpload({ onCompaniesParsed }: CompanyListUploadProps) {
    const [uploading, setUploading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [summary, setSummary] = useState<string | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const parseFile = useCallback(
        async (file: File) => {
            const extension = file.name.split('.').pop()?.toLowerCase() || ''
            if (!ALLOWED_TYPES.includes(extension)) {
                setError(`Unsupported file type: .${extension}. Use CSV, PDF, DOCX, TXT, or MD.`)
                return
            }
            if (file.size > MAX_FILE_SIZE) {
                setError('File too large (max 10 MB)')
                return
            }

            setError(null)
            setSummary(null)
            setUploading(true)
            try {
                const fileContent = await fileToBase64(file)
                const response = await fetch('/api/portfolio/parse-company-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fileType: extension, fileContent }),
                })
                const data = (await response.json()) as ParseResponse & { error?: string }
                if (!response.ok) {
                    throw new Error(data.error || `Could not read the file (${response.status})`)
                }

                const added = onCompaniesParsed(data.companies)
                const skipped = data.companies.length - added
                const parts = [`Added ${added} ${added === 1 ? 'company' : 'companies'}`]
                if (skipped > 0) parts.push(`${skipped} already in the list`)
                if (data.needsUrl > 0) {
                    parts.push(`${data.needsUrl} need a URL before they can be analyzed`)
                }
                setSummary(`${parts.join(' · ')}.`)
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Could not read the file')
            } finally {
                setUploading(false)
                if (fileInputRef.current) fileInputRef.current.value = ''
            }
        },
        [onCompaniesParsed]
    )

    return (
        <div
            className="card-surface-2"
            style={{
                padding: '0.875rem 1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
            }}
        >
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                Upload a CSV with <code>name</code> and <code>url</code> columns (or a PDF/DOCX/TXT/MD list of
                the firm’s companies). A company needs its website URL to be analyzed — any without one are
                added to the list but flagged so you can fill them in.
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.8125rem', padding: '0.375rem 0.75rem' }}
                >
                    {uploading ? 'Reading…' : 'Choose file'}
                </button>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.pdf,.docx,.txt,.md"
                    aria-label="Company list file"
                    onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) void parseFile(file)
                    }}
                    style={{ display: 'none' }}
                />
                {summary && (
                    <span style={{ fontSize: '0.8125rem', color: 'var(--risk-low)' }}>{summary}</span>
                )}
            </div>
            {error && (
                <div role="alert" style={{ color: 'var(--risk-high)', fontSize: '0.75rem' }}>
                    {error}
                </div>
            )}
        </div>
    )
}
