'use client'

import Link from 'next/link'
import { useState } from 'react'

import { useToast } from '@/components/ui'
import type { ConnectedApp } from '@/lib/types/api'

/**
 * Connected Apps settings view — lists the AI assistants the user has connected
 * (their OAuth consents) and lets them disconnect one. Disconnect is optimistic
 * with an undo window (matching the team member-removal pattern); the actual
 * DELETE fires when the undo window closes.
 *
 * Revoking a connection removes the user's consent, so the app must re-approve
 * on its next connection. An already-issued access token keeps working until it
 * expires (within an hour).
 */
export default function ConnectedAppsView({ initialApps }: { initialApps: ConnectedApp[] }) {
    const toast = useToast()
    const [apps, setApps] = useState(initialApps)

    function handleDisconnect(clientId: string, clientName: string) {
        const target = apps.find((app) => app.client_id === clientId)
        if (!target) return
        setApps((prev) => prev.filter((app) => app.client_id !== clientId))
        toast.undo({
            message: `Disconnected ${clientName}`,
            onCommit: async () => {
                try {
                    const res = await fetch(`/api/connected-apps/${clientId}`, { method: 'DELETE' })
                    if (!res.ok) {
                        toast.error('Failed to disconnect app')
                        setApps((prev) => [...prev, target])
                    }
                } catch {
                    toast.error('Failed to disconnect app')
                    setApps((prev) => [...prev, target])
                }
            },
            onUndo: () => {
                setApps((prev) => [...prev, target])
            },
        })
    }

    return (
        <div style={{ maxWidth: '720px' }}>
            <header style={{ marginBottom: '2rem' }}>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                    Connected Apps
                </h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    AI assistants you&rsquo;ve connected to sc0red Services. Disconnecting one requires it to
                    ask for your approval again the next time it connects.
                </p>
            </header>

            <section className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
                {apps.length === 0 ? (
                    <p style={{ color: 'var(--text-tertiary)', fontSize: '0.9375rem' }}>
                        No connected apps yet. Connect an AI assistant to query your portfolio over MCP — see
                        &ldquo;How to connect&rdquo; below.
                    </p>
                ) : (
                    <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                        {apps.map((app) => (
                            <li
                                key={app.client_id}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    gap: '1rem',
                                    padding: '0.75rem 0',
                                    borderBottom: '1px solid var(--border-subtle)',
                                }}
                            >
                                <div style={{ minWidth: 0 }}>
                                    <div
                                        className="truncate"
                                        style={{ fontSize: '0.9375rem', color: 'var(--text-primary)' }}
                                    >
                                        {app.client_name}
                                    </div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                                        {app.consented_at
                                            ? `Connected ${new Date(app.consented_at * 1000).toLocaleDateString()}`
                                            : 'Connected'}
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => handleDisconnect(app.client_id, app.client_name)}
                                    className="btn btn-ghost btn-sm"
                                    style={{ color: 'var(--risk-critical)', flexShrink: 0 }}
                                    aria-label={`Disconnect ${app.client_name}`}
                                >
                                    Disconnect
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            <section className="card" style={{ padding: '1.5rem' }}>
                <h2
                    style={{
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        color: 'var(--text-secondary)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        marginBottom: '0.75rem',
                    }}
                >
                    How to connect
                </h2>
                <ol
                    style={{
                        margin: 0,
                        paddingLeft: '1.25rem',
                        color: 'var(--text-secondary)',
                        fontSize: '0.9375rem',
                        lineHeight: 1.7,
                    }}
                >
                    <li>
                        In your AI assistant, add an MCP server using the <strong>Streamable HTTP</strong>{' '}
                        transport.
                    </li>
                    <li>
                        Use your sc0red Services MCP server URL (ending in <code>/mcp</code>) — ask your
                        administrator if you don&rsquo;t have it.
                    </li>
                    <li>
                        Approve the connection on the consent screen. It will then appear in the list above,
                        and you can disconnect it here any time.
                    </li>
                </ol>
                <p style={{ marginTop: '0.75rem', fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                    <Link href="/settings" style={{ color: 'var(--accent)' }}>
                        ← Back to settings
                    </Link>
                </p>
            </section>
        </div>
    )
}
