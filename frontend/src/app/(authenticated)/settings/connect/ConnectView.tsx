'use client'

import { useState } from 'react'

import { useToast } from '@/components/ui'
import type { ConnectedApp } from '@/lib/types/api'
import { isValidMcpUrl } from '@/lib/utils/mcp'

import ClientSetup from './ClientSetup'
import ServerAddress from './ServerAddress'

/**
 * Connect page — one place to connect an AI assistant to sc0red Services over
 * MCP and manage what's connected: address → set it up → manage. OAuth-only
 * ("Sign in with sc0red"); there is no API-key path. Composes the server-address
 * block and per-client setup, then the customer's OAuth-consent list with
 * disconnect (optimistic + undo, matching the team member-removal pattern).
 */
export default function ConnectView({
    mcpServerUrl,
    initialApps,
}: {
    mcpServerUrl: string
    initialApps: ConnectedApp[]
}) {
    const toast = useToast()
    const [apps, setApps] = useState(initialApps)
    const available = isValidMcpUrl(mcpServerUrl)

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
            onUndo: () => setApps((prev) => [...prev, target]),
        })
    }

    return (
        <div style={{ maxWidth: '720px' }}>
            <header style={{ marginBottom: '2rem' }}>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Connect</h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    Add sc0red Services as a tool in Claude Desktop, Cursor, or any MCP-compatible app —
                    query your portfolio, scans, and risk analyses right from your assistant.
                </p>
            </header>

            <ServerAddress url={available ? mcpServerUrl : ''} available={available} />
            <ClientSetup url={available ? mcpServerUrl : ''} available={available} />

            <section className="card" style={{ padding: '1.5rem' }}>
                <h2 style={SECTION_HEADING}>Connected apps</h2>
                {apps.length === 0 ? (
                    <p style={{ color: 'var(--text-tertiary)', fontSize: '0.9375rem' }}>
                        Nothing connected yet — follow the steps above, then your assistant appears here.
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
                <p style={{ marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                    Disconnecting an app requires it to ask for your approval again the next time it connects.
                </p>
            </section>
        </div>
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
