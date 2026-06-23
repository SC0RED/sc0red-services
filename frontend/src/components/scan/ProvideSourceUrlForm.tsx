import { useState } from 'react'

import { normalizeUserUrl } from '@/lib/utils/url'

interface ProvideSourceUrlFormProps {
    /** Fetch the given page server-side and merge its companies into the scan. */
    onProvideSourceUrl: (url: string) => void
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

// Companion to CompanyListUpload: when discovery missed the right page, the
// customer can point us at a page that lists the portfolio. We read THAT page
// server-side (no web search), so the result stays reliable. Mirrors
// AddCompanyForm's toggle-then-form shape.
export default function ProvideSourceUrlForm({ onProvideSourceUrl }: ProvideSourceUrlFormProps) {
    const [open, setOpen] = useState(false)
    const [url, setUrl] = useState('')
    const [error, setError] = useState('')

    function reset() {
        setUrl('')
        setError('')
    }

    function handleSubmit() {
        if (!url.trim()) {
            setError('Enter the URL of a page that lists the portfolio.')
            return
        }
        // Same normaliser as the main scan input — accepts bare/www hostnames
        // and auto-prepends `https://`.
        const normalized = normalizeUserUrl(url)
        if ('error' in normalized) {
            setError(normalized.error)
            return
        }
        onProvideSourceUrl(normalized.url)
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
                + Provide a page URL
            </button>
        )
    }

    return (
        <div
            className="card-surface-2"
            style={{ padding: '0.875rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
        >
            <div style={{ fontSize: '0.8125rem', fontWeight: 500 }}>
                Paste the URL of a page that lists this firm’s portfolio
            </div>
            <div style={{ color: 'var(--text-tertiary)', fontSize: '0.75rem' }}>
                We’ll read companies directly from that page — a reliable source. If the page builds its list
                in the browser after load, we may still come up short; you can upload your list as a fallback.
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                    // `type="text"` so the parent's `normalizeUserUrl` decides
                    // validity rather than the browser rejecting bare hostnames.
                    type="text"
                    inputMode="url"
                    autoComplete="url"
                    spellCheck={false}
                    placeholder="firm.com/portfolio"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    aria-label="Portfolio page URL"
                    style={FIELD_STYLE}
                />
            </div>
            {error && <div style={{ color: 'var(--risk-high)', fontSize: '0.75rem' }}>{error}</div>}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                    type="button"
                    onClick={handleSubmit}
                    className="btn btn-primary"
                    style={{ fontSize: '0.8125rem', padding: '0.375rem 0.75rem' }}
                >
                    Fetch from this page
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
