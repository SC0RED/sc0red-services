'use client'

import { useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useSession } from 'next-auth/react'
import Image from 'next/image'
import Link from 'next/link'
import { Suspense } from 'react'

import { Button, Card } from '@/components/ui'

function ConsentContent() {
    const searchParams = useSearchParams()
    const { data: session, status } = useSession()
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const clientId = searchParams.get('client_id') || ''
    const clientName = searchParams.get('client_name') || 'Unknown App'
    const redirectUri = searchParams.get('redirect_uri') || ''
    const codeChallenge = searchParams.get('code_challenge') || ''
    const scope = searchParams.get('scope') || 'read write'
    const state = searchParams.get('state') || ''

    if (status === 'loading') {
        return (
            <div
                style={{
                    display: 'flex',
                    minHeight: '100vh',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}
            >
                <div
                    style={{
                        width: '32px',
                        height: '32px',
                        border: '3px solid var(--border)',
                        borderTopColor: 'var(--accent-blue)',
                        borderRadius: '50%',
                        animation: 'spin 1s linear infinite',
                    }}
                />
            </div>
        )
    }

    if (status === 'unauthenticated') {
        const returnUrl = `/oauth/authorize?${searchParams.toString()}`
        return (
            <div
                style={{
                    minHeight: '100vh',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '1.5rem',
                }}
                className="grid-bg"
            >
                <Card padding="lg" style={{ maxWidth: '420px', textAlign: 'center' }}>
                    <p style={{ marginBottom: '1.5rem', color: 'var(--text-secondary)' }}>
                        You need to sign in to authorize <strong>{clientName}</strong>
                    </p>
                    <Link
                        href={`/login?callbackUrl=${encodeURIComponent(returnUrl)}`}
                        className="btn btn-primary"
                        style={{ justifyContent: 'center' }}
                    >
                        Sign In to Continue
                    </Link>
                </Card>
            </div>
        )
    }

    async function handleApprove() {
        setLoading(true)
        setError('')

        try {
            const response = await fetch('/api/oauth/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    client_id: clientId,
                    redirect_uri: redirectUri,
                    code_challenge: codeChallenge,
                    scope,
                    state,
                }),
            })

            const data = await response.json()

            if (!response.ok) {
                setError(data.error || 'Authorization failed')
                setLoading(false)
                return
            }

            // Redirect to client with authorization code
            window.location.href = data.redirect_url
        } catch {
            setError('Failed to authorize. Please try again.')
            setLoading(false)
        }
    }

    function handleDeny() {
        const separator = redirectUri.includes('?') ? '&' : '?'
        const params = new URLSearchParams({ error: 'access_denied' })
        if (state) params.set('state', state)
        window.location.href = `${redirectUri}${separator}${params.toString()}`
    }

    const scopes = scope.split(' ')

    const scopeDescriptions: Record<string, string> = {
        read: 'View your analyses, risk scores, and portfolio data',
        write: 'Run new company and portfolio scans, manage documents',
    }

    return (
        <div
            style={{
                minHeight: '100vh',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '1.5rem',
            }}
            className="grid-bg"
        >
            <div style={{ width: '100%', maxWidth: '460px' }}>
                <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                    <div
                        style={{
                            width: '56px',
                            height: '56px',
                            borderRadius: '12px',
                            overflow: 'hidden',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            marginBottom: '0.75rem',
                        }}
                    >
                        <Image
                            src="/sc0red-services-logo.svg"
                            alt="sc0red Services"
                            width={56}
                            height={56}
                            style={{ objectFit: 'contain' }}
                        />
                    </div>
                </div>

                <Card padding="lg">
                    <h1 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                        Authorize {clientName}
                    </h1>
                    <p
                        style={{
                            color: 'var(--text-secondary)',
                            fontSize: '0.875rem',
                            marginBottom: '1.5rem',
                        }}
                    >
                        <strong>{clientName}</strong> wants to access your sc0red Services account
                    </p>

                    <div
                        style={{
                            padding: '0.75rem 1rem',
                            background: 'var(--bg-surface-2)',
                            borderRadius: 'var(--radius-md)',
                            marginBottom: '1.5rem',
                            fontSize: '0.8125rem',
                        }}
                    >
                        Signed in as <strong>{session?.user?.email}</strong>
                    </div>

                    <div style={{ marginBottom: '1.5rem' }}>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                            This will allow {clientName} to:
                        </div>
                        <ul
                            style={{
                                listStyle: 'none',
                                padding: 0,
                                margin: 0,
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.5rem',
                            }}
                        >
                            {scopes.map((s) => (
                                <li
                                    key={s}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.5rem',
                                        fontSize: '0.875rem',
                                        color: 'var(--text-secondary)',
                                    }}
                                >
                                    <span style={{ color: 'var(--accent-blue)' }}>&#10003;</span>
                                    {scopeDescriptions[s] || s}
                                </li>
                            ))}
                        </ul>
                    </div>

                    {error && (
                        <div className="alert-error" style={{ marginBottom: '1rem' }}>
                            {error}
                        </div>
                    )}

                    <div style={{ display: 'flex', gap: '0.75rem' }}>
                        <button
                            type="button"
                            onClick={handleDeny}
                            className="btn btn-secondary"
                            style={{ flex: 1, justifyContent: 'center' }}
                            disabled={loading}
                        >
                            Cancel
                        </button>
                        <Button
                            type="button"
                            onClick={handleApprove}
                            loading={loading}
                            className="btn-primary"
                            style={{ flex: 1, justifyContent: 'center' }}
                        >
                            {loading ? 'Authorizing...' : 'Allow Access'}
                        </Button>
                    </div>
                </Card>
            </div>
        </div>
    )
}

export default function OAuthAuthorizePage() {
    return (
        <Suspense
            fallback={
                <div
                    style={{
                        display: 'flex',
                        minHeight: '100vh',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    <div
                        style={{
                            width: '32px',
                            height: '32px',
                            border: '3px solid var(--border)',
                            borderTopColor: 'var(--accent-blue)',
                            borderRadius: '50%',
                            animation: 'spin 1s linear infinite',
                        }}
                    />
                </div>
            }
        >
            <ConsentContent />
        </Suspense>
    )
}
