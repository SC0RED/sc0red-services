'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { signIn } from 'next-auth/react'

import { Button, Card, FormField, Input } from '@/components/ui'

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
                            <Image
                                src="/sc0red-services-logo.svg"
                                alt="sc0red Services"
                                width={56}
                                height={56}
                                style={{ objectFit: 'contain' }}
                            />
                        </div>
                        <span style={{ fontSize: '1.375rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                            sc0red Services
                        </span>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                        Start your AI risk assessment
                    </p>
                </div>

                <Card padding="lg">
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
                            <div
                                className="responsive-grid-2"
                                style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}
                            >
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

                        <div
                            className="responsive-grid-2"
                            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}
                        >
                            <FormField label="Your name" htmlFor="name">
                                <Input
                                    id="name"
                                    type="text"
                                    placeholder="Alex Johnson"
                                    value={form.name}
                                    onChange={(e) => update('name', e.target.value)}
                                    required
                                />
                            </FormField>
                            <FormField
                                label={form.orgType === 'pe_firm' ? 'Firm name' : 'Company name'}
                                htmlFor="orgName"
                            >
                                <Input
                                    id="orgName"
                                    type="text"
                                    placeholder={form.orgType === 'pe_firm' ? 'Accel Partners' : 'Acme Corp'}
                                    value={form.orgName}
                                    onChange={(e) => update('orgName', e.target.value)}
                                    required
                                />
                            </FormField>
                        </div>

                        <FormField label="Work email" htmlFor="signup-email">
                            <Input
                                id="signup-email"
                                type="email"
                                placeholder="you@firm.com"
                                value={form.email}
                                onChange={(e) => update('email', e.target.value)}
                                required
                                autoComplete="email"
                            />
                        </FormField>

                        <FormField
                            label="Password"
                            htmlFor="signup-password"
                            helperText="Min. 8 characters with uppercase, lowercase, and numbers"
                        >
                            <Input
                                id="signup-password"
                                type="password"
                                placeholder="••••••••"
                                value={form.password}
                                onChange={(e) => update('password', e.target.value)}
                                required
                                autoComplete="new-password"
                            />
                        </FormField>

                        {error && (
                            <div id="signup-error" role="alert" className="alert-error">
                                {error}
                            </div>
                        )}

                        <Button
                            type="submit"
                            loading={loading}
                            className="w-full"
                            style={{ justifyContent: 'center', marginTop: '0.375rem' }}
                        >
                            {loading ? 'Creating account...' : 'Create Account & Start'}
                        </Button>
                    </form>

                    <div className="divider" style={{ margin: '1.5rem 0' }} />
                    <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        Already have an account?{' '}
                        <Link href="/login" style={{ color: 'var(--accent-blue)', fontWeight: 500 }}>
                            Sign in
                        </Link>
                    </p>
                </Card>
            </div>
        </div>
    )
}
