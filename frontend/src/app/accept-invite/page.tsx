'use client'

import { useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'

import { signInWithCognito, completeNewPasswordChallenge } from '@/lib/auth/cognitoClient'

type Step = 'credentials' | 'success'

function AcceptInviteContent() {
    const searchParams = useSearchParams()
    const emailParam = searchParams.get('email') || ''

    const [email] = useState(emailParam)
    const [tempPassword, setTempPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [step, setStep] = useState<Step>('credentials')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        setLoading(true)
        setError('')

        try {
            const result = await signInWithCognito(email, tempPassword)

            if (result.challengeName === 'NEW_PASSWORD_REQUIRED' && result.cognitoUser) {
                await completeNewPasswordChallenge(result.cognitoUser, newPassword)
                setStep('success')
            } else {
                // User already has a permanent password — just redirect to login
                setStep('success')
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to set password')
        } finally {
            setLoading(false)
        }
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
            <div style={{ width: '100%', maxWidth: '420px' }}>
                <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                    <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Accept Invitation</h1>
                    <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                        Set your password to join sc0red Services
                    </p>
                </div>

                <div className="card" style={{ padding: '2rem' }}>
                    {step === 'credentials' && (
                        <form onSubmit={handleSubmit}>
                            <div className="input-group" style={{ marginBottom: '1rem' }}>
                                <label className="label" htmlFor="email">
                                    Email
                                </label>
                                <input
                                    id="email"
                                    type="email"
                                    className="input"
                                    value={email}
                                    disabled
                                    style={{ opacity: 0.7 }}
                                />
                            </div>
                            <div className="input-group" style={{ marginBottom: '1rem' }}>
                                <label className="label" htmlFor="temp-password">
                                    Temporary Password
                                </label>
                                <input
                                    id="temp-password"
                                    type="password"
                                    className="input"
                                    value={tempPassword}
                                    onChange={(e) => setTempPassword(e.target.value)}
                                    required
                                    placeholder="From your invitation email"
                                    autoComplete="one-time-code"
                                />
                            </div>
                            <div className="input-group" style={{ marginBottom: '1rem' }}>
                                <label className="label" htmlFor="new-password">
                                    New Password
                                </label>
                                <input
                                    id="new-password"
                                    type="password"
                                    className="input"
                                    value={newPassword}
                                    onChange={(e) => setNewPassword(e.target.value)}
                                    required
                                    minLength={8}
                                    autoComplete="new-password"
                                    placeholder="At least 8 characters"
                                />
                            </div>
                            {error && (
                                <div role="alert" className="alert-error" style={{ marginBottom: '1rem' }}>
                                    {error}
                                </div>
                            )}
                            <button
                                type="submit"
                                className="btn btn-primary"
                                style={{ width: '100%' }}
                                disabled={loading}
                            >
                                {loading ? 'Setting password...' : 'Set Password & Join'}
                            </button>
                        </form>
                    )}

                    {step === 'success' && (
                        <div style={{ textAlign: 'center' }}>
                            <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                                Your password has been set. You can now log in.
                            </p>
                            <Link
                                href="/login"
                                className="btn btn-primary"
                                style={{ width: '100%', justifyContent: 'center' }}
                            >
                                Go to Login
                            </Link>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

export default function AcceptInvitePage() {
    return (
        <Suspense
            fallback={
                <div
                    style={{
                        minHeight: '100vh',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    Loading...
                </div>
            }
        >
            <AcceptInviteContent />
        </Suspense>
    )
}
