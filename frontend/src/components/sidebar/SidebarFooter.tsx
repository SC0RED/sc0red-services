'use client'

import { signOut, useSession } from 'next-auth/react'
import { useEffect, useState } from 'react'

import { useShortcutsUi } from '@/components/ui/ShortcutsUi'

/**
 * Sidebar footer — the signed-in user block plus a dull, always-present
 * discoverability affordance for the command palette and keyboard-shortcuts
 * help. The affordance is CLICKABLE (not just a "press ?" hint) so mouse users
 * and assistive tech can reach both, which is the whole point — the shortcut to
 * open the shortcuts list is otherwise impossible to discover.
 */
export default function SidebarFooter() {
    const { data: session } = useSession()
    const { openPalette, openShortcuts } = useShortcutsUi()
    // Seed a safe server default (Ctrl) and correct it on the client after mount,
    // so the label never causes an SSR/CSR hydration mismatch on Mac.
    const [isMac, setIsMac] = useState(false)
    useEffect(() => {
        setIsMac(/Mac|iP(hone|ad|od)/i.test(navigator.platform))
    }, [])

    return (
        <div style={{ padding: '0.75rem 0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
            <div
                style={{
                    display: 'flex',
                    gap: '0.75rem',
                    padding: '0 0.75rem 0.5rem',
                    fontSize: '0.6875rem',
                    color: 'var(--text-tertiary)',
                }}
            >
                <button type="button" onClick={openPalette} style={HINT_BUTTON} aria-label="Open command palette">
                    <kbd style={KBD}>{isMac ? '⌘K' : 'Ctrl K'}</kbd> commands
                </button>
                <button type="button" onClick={openShortcuts} style={HINT_BUTTON} aria-label="Show keyboard shortcuts">
                    <kbd style={KBD}>?</kbd> shortcuts
                </button>
            </div>

            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.625rem',
                    padding: '0.5rem 0.75rem',
                    borderRadius: 'var(--radius-md)',
                }}
            >
                <div
                    style={{
                        width: '30px',
                        height: '30px',
                        borderRadius: '50%',
                        flexShrink: 0,
                        background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        color: '#fff',
                    }}
                >
                    {session?.user?.name?.[0]?.toUpperCase() || 'U'}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="truncate" style={{ fontSize: '0.8125rem', fontWeight: 500 }}>
                        {session?.user?.name || 'User'}
                    </div>
                    <div
                        className="truncate"
                        style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}
                    >
                        {session?.user?.email}
                    </div>
                </div>
                <button
                    onClick={() => signOut({ callbackUrl: '/login' })}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--text-tertiary)',
                        cursor: 'pointer',
                        padding: '4px',
                    }}
                    title="Sign out"
                    aria-label="Sign out"
                >
                    <svg
                        width="15"
                        height="15"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                        <polyline points="16 17 21 12 16 7" />
                        <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                </button>
            </div>
        </div>
    )
}

const HINT_BUTTON = {
    background: 'none',
    border: 'none',
    padding: 0,
    color: 'inherit',
    cursor: 'pointer',
    fontSize: 'inherit',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.25rem',
}
const KBD = {
    fontSize: '0.625rem',
    padding: '0 0.25rem',
    border: '1px solid var(--border-subtle)',
    borderRadius: '3px',
    color: 'var(--text-secondary)',
}
