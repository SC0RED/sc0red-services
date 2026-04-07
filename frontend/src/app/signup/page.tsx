'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { signIn } from 'next-auth/react'

export default function SignupPage() {
    const router = useRouter()
    const [form, setForm] = useState({
        name: '',
        email: '',
        password: '',
        orgName: '',
        orgType: 'pe_firm',
    })
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    function update(field: string, val: string) {
        setForm((f) => ({ ...f, [field]: val }))
    }

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        setLoading(true)
        setError('')

        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(form),
        })
        const data = await res.json()

        if (!res.ok) {
            setError(data.error || 'Registration failed')
            setLoading(false)
            return
        }

        // Auto sign in
        await signIn('credentials', { email: form.email, password: form.password, redirect: false })
        router.push('/dashboard')
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
                <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
                    <div
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.625rem',
                            marginBottom: '0.75rem',
                        }}
                    >
                        <div
                            style={{
                                width: '56px',
                                height: '56px',
                                borderRadius: '12px',
                                overflow: 'hidden',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                            }}
                        >
                            <img
                                src="/janus-logo.png"
                                alt="Janus"
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            />
                        </div>
                        <span style={{ fontSize: '1.375rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                            Janus
                        </span>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                        Start your AI risk assessment
                    </p>
                </div>

                <div className="card" style={{ padding: '2rem' }}>
                    <h1 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.375rem' }}>
                        Create your account
                    </h1>
                    <p
                        style={{
                            color: 'var(--text-secondary)',
                            fontSize: '0.875rem',
                            marginBottom: '1.75rem',
                        }}
                    >
                        Get started with your first analysis in minutes
                    </p>

                    <form
                        onSubmit={handleSubmit}
                        style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}
                    >
                        {/* Org Type Toggle */}
                        <div className="input-group">
                            <label className="label">Account type</label>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                                {[
                                    { value: 'pe_firm', label: 'PE Firm', desc: 'Analyze portfolio' },
                                    { value: 'company', label: 'Company', desc: 'Standalone scan' },
                                ].map((opt) => (
                                    <button
                                        key={opt.value}
                                        type="button"
                                        onClick={() => update('orgType', opt.value)}
                                        style={{
                                            padding: '0.75rem',
                                            borderRadius: 'var(--radius-md)',
                                            border:
                                                form.orgType === opt.value
                                                    ? '2px solid var(--accent-blue)'
                                                    : '1px solid var(--border)',
                                            background:
                                                form.orgType === opt.value
                                                    ? 'rgba(59,123,246,0.08)'
                                                    : 'var(--bg-surface)',
                                            color:
                                                form.orgType === opt.value
                                                    ? 'var(--accent-blue)'
                                                    : 'var(--text-secondary)',
                                            textAlign: 'left',
                                            cursor: 'pointer',
                                            transition: 'all var(--transition-fast)',
                                        }}
                                    >
                                        <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                                            {opt.label}
                                        </div>
                                        <div style={{ fontSize: '0.75rem', opacity: 0.7, marginTop: '2px' }}>
                                            {opt.desc}
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
                            <div className="input-group">
                                <label className="label" htmlFor="name">
                                    Your name
                                </label>
                                <input
                                    id="name"
                                    type="text"
                                    className="input"
                                    placeholder="Alex Johnson"
                                    value={form.name}
                                    onChange={(e) => update('name', e.target.value)}
                                    required
                                />
                            </div>
                            <div className="input-group">
                                <label className="label" htmlFor="orgName">
                                    {form.orgType === 'pe_firm' ? 'Firm name' : 'Company name'}
                                </label>
                                <input
                                    id="orgName"
                                    type="text"
                                    className="input"
                                    placeholder={form.orgType === 'pe_firm' ? 'Accel Partners' : 'Acme Corp'}
                                    value={form.orgName}
                                    onChange={(e) => update('orgName', e.target.value)}
                                    required
                                />
                            </div>
                        </div>

                        <div className="input-group">
                            <label className="label" htmlFor="signup-email">
                                Work email
                            </label>
                            <input
                                id="signup-email"
                                type="email"
                                className="input"
                                placeholder="you@firm.com"
                                value={form.email}
                                onChange={(e) => update('email', e.target.value)}
                                required
                                autoComplete="email"
                                aria-describedby={error ? 'signup-error' : undefined}
                            />
                        </div>

                        <div className="input-group">
                            <label className="label" htmlFor="signup-password">
                                Password
                            </label>
                            <input
                                id="signup-password"
                                type="password"
                                className="input"
                                placeholder="Min. 8 characters"
                                value={form.password}
                                onChange={(e) => update('password', e.target.value)}
                                required
                                autoComplete="new-password"
                            />
                        </div>

                        {error && (
                            <div id="signup-error" role="alert" className="alert-error">
                                {error}
                            </div>
                        )}

                        <button
                            type="submit"
                            className="btn btn-primary w-full"
                            style={{ justifyContent: 'center', marginTop: '0.375rem' }}
                            disabled={loading}
                        >
                            {loading ? 'Creating account...' : 'Create Account & Start'}
                        </button>
                    </form>

                    <div className="divider" style={{ margin: '1.5rem 0' }} />
                    <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        Already have an account?{' '}
                        <Link href="/login" style={{ color: 'var(--accent-blue)', fontWeight: 500 }}>
                            Sign in
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    )
}
