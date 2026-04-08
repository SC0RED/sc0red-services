'use client'

import { useState } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'

import { Button, Card, FormField, Input } from '@/components/ui'

export default function LoginPage() {
    const router = useRouter()
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        setLoading(true)
        setError('')

        const res = await signIn('credentials', {
            email,
            password,
            redirect: false,
        })

        if (res?.ok) {
            router.push('/dashboard')
        } else {
            setError('Invalid email or password')
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
                {/* Logo */}
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
                                src="/janus-logo.png"
                                alt="Janus"
                                width={56}
                                height={56}
                                style={{ objectFit: 'cover' }}
                            />
                        </div>
                        <span style={{ fontSize: '1.375rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
                            Janus
                        </span>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                        AI Risk & Opportunity Intelligence
                    </p>
                </div>

                <Card padding="lg">
                    <h1 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.375rem' }}>
                        Welcome back
                    </h1>
                    <p
                        style={{
                            color: 'var(--text-secondary)',
                            fontSize: '0.875rem',
                            marginBottom: '1.75rem',
                        }}
                    >
                        Sign in to your account
                    </p>

                    <form
                        onSubmit={handleSubmit}
                        style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}
                    >
                        <FormField label="Email" htmlFor="email">
                            <Input
                                id="email"
                                type="email"
                                placeholder="you@firm.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                autoComplete="email"
                            />
                        </FormField>

                        <FormField label="Password" htmlFor="password">
                            <Input
                                id="password"
                                type="password"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                autoComplete="current-password"
                            />
                            <div style={{ textAlign: 'right', marginTop: '0.375rem' }}>
                                <Link
                                    href="/forgot-password"
                                    style={{ color: 'var(--accent-blue)', fontSize: '0.8125rem' }}
                                >
                                    Forgot password?
                                </Link>
                            </div>
                        </FormField>

                        {error && (
                            <div id="login-error" role="alert" className="alert-error">
                                {error}
                            </div>
                        )}

                        <Button
                            type="submit"
                            loading={loading}
                            className="w-full"
                            style={{ justifyContent: 'center', marginTop: '0.25rem' }}
                        >
                            {loading ? 'Signing in...' : 'Sign In'}
                        </Button>
                    </form>

                    <div className="divider" style={{ margin: '1.5rem 0' }} />
                    <p style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                        Don&apos;t have an account?{' '}
                        <Link href="/signup" style={{ color: 'var(--accent-blue)', fontWeight: 500 }}>
                            Create one
                        </Link>
                    </p>
                </Card>
            </div>
        </div>
    )
}
