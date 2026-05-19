'use client'

import { useState } from 'react'
import { signIn } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'

import { Button, Card, FormField, Input } from '@/components/ui'

const MARKETING_URL = process.env.NEXT_PUBLIC_MARKETING_URL ?? 'https://www.sc0red.com'

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
            className="grid-bg flex-col justify-center items-center"
            style={{ minHeight: '100vh', padding: '1.5rem' }}
        >
            <div className="w-full max-w-sm">
                {/* Logo */}
                <div className="text-center mb-xl">
                    <div className="inline-flex items-center mb-sm">
                        <Image
                            src="/sc0red-logo-white.svg"
                            alt="sc0red"
                            width={158}
                            height={43}
                            style={{ height: '40px', width: 'auto' }}
                            priority
                        />
                    </div>
                    <p className="text-secondary" style={{ fontSize: '0.9375rem' }}>
                        AI Risk &amp; Strategic Intelligence
                    </p>
                    <p style={{ marginTop: '0.625rem', fontSize: '0.8125rem' }}>
                        <a
                            href={MARKETING_URL}
                            style={{ color: 'var(--text-tertiary)', textDecoration: 'none' }}
                        >
                            ← Back to sc0red.com
                        </a>
                    </p>
                </div>

                <Card padding="lg">
                    <h1 className="font-bold mb-xs" style={{ fontSize: '1.25rem' }}>
                        Welcome back
                    </h1>
                    <p className="text-secondary text-sm mb-lg">Sign in to your account</p>

                    <form onSubmit={handleSubmit} className="flex-col gap-lg">
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
                    <p className="text-center text-secondary text-sm">
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
