'use client'

import { useState, useRef, useCallback } from 'react'

import ReanalyzeProgressCard from '@/components/analysis/ReanalyzeProgressCard'
import type { DocumentInfo } from '@/lib/types/api'

/**
 * Stable DOM id for the in-section progress card. Used so the
 * re-analyze button can wire `aria-describedby` to the card when the
 * card is rendered — screen readers then announce the progress state
 * alongside the button's accessible name on focus, instead of just
 * the static label.
 */
const REANALYZE_PROGRESS_ID = 'reanalyze-progress'

const ALLOWED_TYPES = ['pdf', 'docx', 'xlsx', 'xls', 'txt', 'csv', 'md']
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB

interface DocumentUploadProps {
    analysisId: string
    documents: DocumentInfo[]
    onDocumentsChange: () => void
    onReanalyze?: () => void
    reanalyzing?: boolean
    /**
     * Latest progress label from the re-analyze pipeline. Optional
     * because not every caller wires the realtime hook (e.g., simple
     * test renderings). When provided alongside `reanalyzing === true`,
     * surfaces inside the in-section progress block.
     */
    reanalysisLabel?: string
    /**
     * Latest progress percentage (0-100) from the re-analyze pipeline.
     * Same optionality contract as `reanalysisLabel`.
     */
    reanalysisProgress?: number
    /**
     * Error from the parent's re-analyze polling loop. Rendered as an
     * alert inside this section so the document-related error surface
     * is unified — DocumentUpload's internal upload/delete errors and
     * the reanalyze loop's polling errors live in one visual region.
     */
    documentError?: string | null
}

function formatCharCount(count: number): string {
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K chars`
    return `${count} chars`
}

/**
 * Document-upload widget — the leaf component for the "improve this
 * analysis" loop. Three concerns are colocated here:
 *   1. File drag-drop / click upload + per-document delete
 *   2. Explicit "Re-analyze with Documents" button to kick off the
 *      re-analysis pipeline against the uploaded context
 *   3. In-section progress display while re-analysis runs (label +
 *      progress bar + percent readout) — co-located with the button
 *      that triggers it, NOT rendered as an orphan sibling on the page
 *
 * Section framing (heading, lead copy) is owned by the consuming page,
 * not this widget. `AnalysisDetail` wraps this with an "Improve This
 * Analysis" heading + lead; `FailedAnalysisView` wraps it with
 * "Upload supporting documents (optional)" + its own retry UI. Keeping
 * framing at the page level matches the section-wrapper pattern set in
 * `redesign-analysis-detail-narrative` D5.
 */
export default function DocumentUpload({
    analysisId,
    documents,
    onDocumentsChange,
    onReanalyze,
    reanalyzing = false,
    reanalysisLabel,
    reanalysisProgress,
    documentError,
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
        <div className="analysis-section-spacing">
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
                                fontSize: '0.75rem',
                                color: 'var(--text-tertiary)',
                            }}
                        >
                            PDF, DOCX, XLSX, TXT, CSV, MD (max 10 MB)
                        </p>
                    </>
                )}
            </div>

            {error && (
                <div className="alert-error" style={{ marginBottom: '1rem' }} role="alert">
                    {error}
                </div>
            )}

            {/* Re-analyze polling error from the parent. Different surface
                than `error` (which is upload/delete failures inside this
                component) — both are document-related so they live next
                to each other. */}
            {documentError && (
                <div className="alert-error" style={{ marginBottom: '1rem' }} role="alert">
                    {documentError}
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
                            className="card card--list"
                            style={{
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
                                    fontSize: '0.75rem',
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

            {/* Re-analyze button. While re-analysis is in flight,
                `aria-describedby` points at the progress card so screen
                readers announce progress state alongside the button's
                accessible name on focus. */}
            {documents.length > 0 && onReanalyze && (
                <button
                    onClick={onReanalyze}
                    disabled={reanalyzing}
                    aria-label={
                        reanalyzing ? 'Re-analysis in progress' : 'Re-analyze with uploaded documents'
                    }
                    aria-describedby={reanalyzing ? REANALYZE_PROGRESS_ID : undefined}
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

            {/* Re-analyze progress — co-located with the button that
                triggers it. Previously rendered as a sibling block in
                AnalysisDetail.tsx, which placed the progress bar above
                the trigger and orphaned it from its affordance. */}
            {reanalyzing && (
                <ReanalyzeProgressCard
                    id={REANALYZE_PROGRESS_ID}
                    label={reanalysisLabel}
                    progress={reanalysisProgress}
                />
            )}
        </div>
    )
}
