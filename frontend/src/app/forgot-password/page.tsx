'use client'

import { useState } from 'react'
import Link from 'next/link'

import { forgotPassword, confirmForgotPassword } from '@/lib/auth/cognitoClient'

type Step = 'email' | 'code' | 'success'

export default function ForgotPasswordPage() {
    const [step, setStep] = useState<Step>('email')
    const [email, setEmail] = useState('')
    const [code, setCode] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    async function handleRequestCode(e: React.FormEvent) {
        e.preventDefault()
        setLoading(true)
        setError('')
        try {
            await forgotPassword(email)
            setStep('code')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to send reset code')
        } finally {
            setLoading(false)
        }
    }

    async function handleResetPassword(e: React.FormEvent) {
        e.preventDefault()
        setLoading(true)
        setError('')
        try {
            await confirmForgotPassword(email, code, newPassword)
            setStep('success')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to reset password')
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
                    <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>Reset Password</h1>
                </div>

                <div className="card" style={{ padding: '2rem' }}>
                    {step === 'email' && (
                        <form onSubmit={handleRequestCode}>
                            <p
                                style={{
                                    color: 'var(--text-secondary)',
                                    marginBottom: '1.5rem',
                                    fontSize: '0.875rem',
                                }}
                            >
                                Enter your email and we will send you a verification code.
                            </p>
                            <div className="input-group" style={{ marginBottom: '1rem' }}>
                                <label className="label" htmlFor="email">
                                    Email
                                </label>
                                <input
                                    id="email"
                                    type="email"
                                    className="input"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required
                                    autoComplete="email"
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
                                {loading ? 'Sending...' : 'Send Reset Code'}
                            </button>
                        </form>
                    )}

                    {step === 'code' && (
                        <form onSubmit={handleResetPassword}>
                            <p
                                style={{
                                    color: 'var(--text-secondary)',
                                    marginBottom: '1.5rem',
                                    fontSize: '0.875rem',
                                }}
                            >
                                Check your email for a verification code.
                            </p>
                            <div className="input-group" style={{ marginBottom: '1rem' }}>
                                <label className="label" htmlFor="code">
                                    Verification Code
                                </label>
                                <input
                                    id="code"
                                    type="text"
                                    className="input"
                                    value={code}
                                    onChange={(e) => setCode(e.target.value)}
                                    required
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
                                    autoComplete="new-password"
                                    minLength={8}
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
                                {loading ? 'Resetting...' : 'Reset Password'}
                            </button>
                        </form>
                    )}

                    {step === 'success' && (
                        <div style={{ textAlign: 'center' }}>
                            <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                                Your password has been reset successfully.
                            </p>
                            <Link
                                href="/login"
                                className="btn btn-primary"
                                style={{ width: '100%', justifyContent: 'center' }}
                            >
                                Back to Login
                            </Link>
                        </div>
                    )}
                </div>

                <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
                    <Link href="/login" style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        Back to Login
                    </Link>
                </div>
            </div>
        </div>
    )
}
