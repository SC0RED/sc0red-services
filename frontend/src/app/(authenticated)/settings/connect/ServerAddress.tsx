'use client'

import { useState } from 'react'

import { useToast } from '@/components/ui'

/**
 * Section ① of the Connect page — the customer's MCP server address with a Copy
 * button. When the address is unavailable (not a valid https://…/mcp URL) the
 * block shows a clear unavailable state and disables Copy, rather than rendering
 * a blank or broken address.
 */
export default function ServerAddress({
    url,
    available,
}: {
    url: string
    available: boolean
}) {
    const toast = useToast()
    const [copied, setCopied] = useState(false)

    async function handleCopy() {
        try {
            await navigator.clipboard.writeText(url)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
        } catch {
            toast.error('Could not copy to clipboard')
        }
    }

    return (
        <section className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <h2 style={SECTION_HEADING}>Your server address</h2>
            {available ? (
                <>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'stretch' }}>
                        <code
                            data-testid="mcp-server-address"
                            style={{
                                flex: 1,
                                padding: '0.625rem 0.75rem',
                                background: 'var(--surface-sunken)',
                                border: '1px solid var(--border-subtle)',
                                borderRadius: 'var(--radius-md)',
                                fontSize: '0.875rem',
                                overflowX: 'auto',
                                whiteSpace: 'nowrap',
                            }}
                        >
                            {url}
                        </code>
                        <button
                            type="button"
                            onClick={handleCopy}
                            className="btn btn-secondary btn-sm"
                            style={{ flexShrink: 0 }}
                            aria-label="Copy server address"
                        >
                            {copied ? 'Copied' : 'Copy'}
                        </button>
                    </div>
                    <p style={{ marginTop: '0.75rem', fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                        You&rsquo;ll sign in with sc0red when your client prompts — nothing else to copy or
                        store.
                    </p>
                </>
            ) : (
                <p
                    data-testid="mcp-address-unavailable"
                    style={{ color: 'var(--text-tertiary)', fontSize: '0.9375rem' }}
                >
                    Your MCP server address isn&rsquo;t available in this environment yet. Once it&rsquo;s
                    provisioned it will appear here — no need to ask an administrator.
                </p>
            )}
        </section>
    )
}

const SECTION_HEADING = {
    fontSize: '0.875rem',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    marginBottom: '0.75rem',
}
