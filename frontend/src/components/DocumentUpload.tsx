'use client'

import { useState, useRef, useCallback } from 'react'
import type { DocumentInfo } from '@/lib/types/api'

const ALLOWED_TYPES = ['pdf', 'docx', 'xlsx', 'xls', 'txt', 'csv', 'md']
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

interface DocumentUploadProps {
    analysisId: string
    documents: DocumentInfo[]
    onDocumentsChange: () => void
    onReanalyze?: () => void
    reanalyzing?: boolean
}

function formatCharCount(count: number): string {
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K chars`
    return `${count} chars`
}

export default function DocumentUpload({
    analysisId,
    documents,
    onDocumentsChange,
    onReanalyze,
    reanalyzing = false,
}: DocumentUploadProps) {
    const [uploading, setUploading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [dragOver, setDragOver] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const uploadFile = useCallback(
        async (file: File) => {
            const extension = file.name.split('.').pop()?.toLowerCase() || ''
            if (!ALLOWED_TYPES.includes(extension)) {
                setError(`Unsupported file type: .${extension}`)
                return
            }
            if (file.size > MAX_FILE_SIZE) {
                setError('File too large (max 10 MB)')
                return
            }

            setError(null)
            setUploading(true)

            try {
                let documentKey = ''

                // Try S3 presigned URL upload first
                const urlResponse = await fetch(`/api/analysis/${analysisId}/upload-url`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: file.name, fileType: extension }),
                })

                if (urlResponse.ok) {
                    const { uploadUrl, documentKey: key } = (await urlResponse.json()) as {
                        uploadUrl: string
                        documentKey: string
                    }
                    const putResponse = await fetch(uploadUrl, {
                        method: 'PUT',
                        body: file,
                        headers: { 'Content-Type': 'application/octet-stream' },
                    })
                    if (!putResponse.ok) throw new Error('Failed to upload file to storage')
                    documentKey = key
                }

                // Register document — with S3 key if available, otherwise base64 fallback
                const payload: Record<string, string> = {
                    filename: file.name,
                    fileType: extension,
                }
                if (documentKey) {
                    payload.documentKey = documentKey
                } else {
                    const buffer = await file.arrayBuffer()
                    payload.fileContent = btoa(
                        new Uint8Array(buffer).reduce((data, byte) => data + String.fromCharCode(byte), '')
                    )
                }

                const response = await fetch(`/api/analysis/${analysisId}/documents`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                })

                if (!response.ok) {
                    const body = (await response.json()) as { error?: string }
                    throw new Error(body.error || `Upload failed: ${response.status}`)
                }

                onDocumentsChange()
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Upload failed')
            } finally {
                setUploading(false)
            }
        },
        [analysisId, onDocumentsChange]
    )

    const handleDrop = useCallback(
        (event: React.DragEvent) => {
            event.preventDefault()
            setDragOver(false)
            const file = event.dataTransfer.files[0]
            if (file) uploadFile(file)
        },
        [uploadFile]
    )

    const handleFileSelect = useCallback(
        (event: React.ChangeEvent<HTMLInputElement>) => {
            const file = event.target.files?.[0]
            if (file) uploadFile(file)
            if (fileInputRef.current) fileInputRef.current.value = ''
        },
        [uploadFile]
    )

    const handleDelete = useCallback(
        async (documentId: string) => {
            try {
                const response = await fetch(`/api/analysis/${analysisId}/documents/${documentId}`, {
                    method: 'DELETE',
                })
                if (!response.ok) throw new Error('Delete failed')
                onDocumentsChange()
            } catch {
                setError('Failed to delete document')
            }
        },
        [analysisId, onDocumentsChange]
    )

    return (
        <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>Documents</h2>

            {/* Drop zone */}
            <div
                data-testid="drop-zone"
                onDragOver={(e) => {
                    e.preventDefault()
                    setDragOver(true)
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                style={{
                    border: `2px dashed ${dragOver ? 'var(--accent-blue)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius-md)',
                    padding: '2rem',
                    textAlign: 'center',
                    cursor: 'pointer',
                    background: dragOver ? 'rgba(59,123,246,0.05)' : 'var(--bg-surface)',
                    transition: 'all var(--transition-fast)',
                    marginBottom: '1rem',
                }}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.xlsx,.xls,.txt,.csv,.md"
                    onChange={handleFileSelect}
                    style={{ display: 'none' }}
                />
                {uploading ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Uploading...</p>
                ) : (
                    <>
                        <p style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
                            Drop a file here or click to browse
                        </p>
                        <p
                            style={{
                                fontSize: '0.8rem',
                                color: 'var(--text-tertiary)',
                            }}
                        >
                            PDF, DOCX, XLSX, TXT, CSV, MD (max 10 MB)
                        </p>
                    </>
                )}
            </div>

            {error && (
                <div
                    style={{
                        padding: '0.75rem 1rem',
                        background: 'rgba(239,68,68,0.1)',
                        borderRadius: 'var(--radius-sm)',
                        color: 'var(--risk-critical)',
                        fontSize: '0.875rem',
                        marginBottom: '1rem',
                    }}
                >
                    {error}
                </div>
            )}

            {/* Document list */}
            {documents.length > 0 && (
                <div
                    style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}
                >
                    {documents.map((doc) => (
                        <div
                            key={doc.id}
                            className="card"
                            style={{
                                padding: '0.75rem 1rem',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                            }}
                        >
                            <div>
                                <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>{doc.filename}</span>
                                <span
                                    style={{
                                        marginLeft: '0.75rem',
                                        fontSize: '0.75rem',
                                        color: 'var(--text-tertiary)',
                                    }}
                                >
                                    {formatCharCount(doc.charCount)}
                                </span>
                            </div>
                            <button
                                onClick={() => handleDelete(doc.id)}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    color: 'var(--risk-critical)',
                                    cursor: 'pointer',
                                    fontSize: '0.8rem',
                                    fontWeight: 500,
                                    padding: '0.25rem 0.5rem',
                                }}
                            >
                                Remove
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* Re-analyze button */}
            {documents.length > 0 && onReanalyze && (
                <button
                    onClick={onReanalyze}
                    disabled={reanalyzing}
                    style={{
                        padding: '0.625rem 1.25rem',
                        background: reanalyzing ? 'var(--bg-surface-3)' : 'var(--accent-blue)',
                        color: reanalyzing ? 'var(--text-tertiary)' : '#fff',
                        border: 'none',
                        borderRadius: 'var(--radius-md)',
                        fontWeight: 600,
                        fontSize: '0.875rem',
                        cursor: reanalyzing ? 'not-allowed' : 'pointer',
                    }}
                >
                    {reanalyzing ? 'Re-analyzing...' : 'Re-analyze with Documents'}
                </button>
            )}
        </div>
    )
}
