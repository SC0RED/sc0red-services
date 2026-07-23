'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { signOut, useSession } from 'next-auth/react'

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    const { data: session } = useSession()
    const [signingOut, setSigningOut] = useState(false)

    // If the user has a session but the page errored, the most likely cause
    // is an expired Cognito token. Auto-sign them out so they can re-auth.
    useEffect(() => {
        if (session && !signingOut) {
            setSigningOut(true)
            signOut({ callbackUrl: '/login' })
        }
    }, [session, signingOut])

    if (signingOut) {
        return (
            <div
                style={{
                    display: 'flex',
                    minHeight: '100vh',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '2rem',
                }}
            >
                {/* Honest copy: this boundary fires on ANY page error while a
                    session exists (including backend outages), so it must not
                    diagnose "session expired" — that sent users chasing password
                    resets during a 502 outage. State what we know: the page
                    failed and we're signing out for a clean retry. */}
                <div className="card" style={{ padding: '3rem', textAlign: 'center', maxWidth: '480px' }}>
                    <h1 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                        Something went wrong
                    </h1>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                        We couldn&apos;t load this page. Redirecting to login so you can try
                        again — if this keeps happening, the problem is on our side, not
                        your password.
                    </p>
                </div>
            </div>
        )
    }

    return (
        <div
            style={{
                display: 'flex',
                minHeight: '100vh',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '2rem',
            }}
        >
            <div className="card" style={{ padding: '3rem', textAlign: 'center', maxWidth: '480px' }}>
                <div
                    style={{
                        width: '64px',
                        height: '64px',
                        margin: '0 auto 1.5rem',
                        borderRadius: '50%',
                        background: 'var(--risk-critical-bg)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    <svg
                        width="28"
                        height="28"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="var(--risk-critical)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="8" x2="12" y2="12" />
                        <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                </div>

                <h1 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                    Something went wrong
                </h1>
                <p
                    style={{
                        color: 'var(--text-secondary)',
                        fontSize: '0.9375rem',
                        marginBottom: '0.5rem',
                        lineHeight: 1.6,
                    }}
                >
                    An unexpected error occurred while loading this page.
                </p>
                {error.message && (
                    <p
                        style={{
                            color: 'var(--text-tertiary)',
                            fontSize: '0.8125rem',
                            marginBottom: '2rem',
                            fontFamily: 'var(--font-mono)',
                        }}
                    >
                        {error.message}
                    </p>
                )}

                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
                    <button onClick={reset} className="btn btn-primary">
                        Try again
                    </button>
                    <Link href="/dashboard" className="btn btn-ghost">
                        Go to Dashboard
                    </Link>
                </div>
            </div>
        </div>
    )
}
