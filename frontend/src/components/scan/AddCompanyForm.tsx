import { useState } from 'react'

import { normalizeUserUrl } from '@/lib/utils/url'

interface AddCompanyFormProps {
    existingUrls: string[]
    onAdd: (name: string, url: string) => void
}

const FIELD_STYLE: React.CSSProperties = {
    flex: 1,
    padding: '0.5rem 0.75rem',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)',
    background: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    fontSize: '0.8125rem',
}

export default function AddCompanyForm({ existingUrls, onAdd }: AddCompanyFormProps) {
    const [open, setOpen] = useState(false)
    const [name, setName] = useState('')
    const [url, setUrl] = useState('')
    const [error, setError] = useState('')

    function reset() {
        setName('')
        setUrl('')
        setError('')
    }

    function handleAdd() {
        const trimmedName = name.trim()
        if (!trimmedName || !url.trim()) {
            setError('Both name and URL are required.')
            return
        }
        // Same normaliser as the main scan input — accepts bare/www hostnames
        // and auto-prepends `https://`.
        const normalized = normalizeUserUrl(url)
        if ('error' in normalized) {
            setError(normalized.error)
            return
        }
        if (existingUrls.includes(normalized.url)) {
            setError('This URL is already in the list.')
            return
        }
        onAdd(trimmedName, normalized.url)
        reset()
        setOpen(false)
    }

    if (!open) {
        return (
            <button
                type="button"
                onClick={() => setOpen(true)}
                className="btn btn-ghost"
                style={{ fontSize: '0.8125rem', padding: '0.375rem 0.75rem' }}
            >
                + Add Company Manually
            </button>
        )
    }

    return (
        <div
            className="card-surface-2"
            style={{ padding: '0.875rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
        >
            <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                    type="text"
                    placeholder="Company Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    aria-label="Company Name"
                    style={FIELD_STYLE}
                />
                <input
                    // `type="text"` so the parent's `normalizeUserUrl` decides
                    // validity rather than the browser rejecting bare hostnames.
                    type="text"
                    inputMode="url"
                    autoComplete="url"
                    spellCheck={false}
                    placeholder="company.com"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    aria-label="Company URL"
                    style={FIELD_STYLE}
                />
            </div>
            {error && <div style={{ color: 'var(--risk-high)', fontSize: '0.75rem' }}>{error}</div>}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                    type="button"
                    onClick={handleAdd}
                    className="btn btn-primary"
                    style={{ fontSize: '0.8125rem', padding: '0.375rem 0.75rem' }}
                >
                    Add
                </button>
                <button
                    type="button"
                    onClick={() => {
                        reset()
                        setOpen(false)
                    }}
                    className="btn btn-ghost"
                    style={{ fontSize: '0.8125rem', padding: '0.375rem 0.75rem' }}
                >
                    Cancel
                </button>
            </div>
        </div>
    )
}
