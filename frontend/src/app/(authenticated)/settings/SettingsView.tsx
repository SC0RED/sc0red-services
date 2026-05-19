'use client'

import { signOut, useSession } from 'next-auth/react'
import { useEffect, useRef, useState } from 'react'

import ThemeToggle from '@/components/ThemeToggle'
import { useToast } from '@/components/ui'

/**
 * Settings page — Tier 1 §4.
 *
 * Read-only profile display + org info with copy-to-clipboard, plus a
 * dedicated "Sign out" affordance. The sidebar's icon-button signout
 * stays — Settings becomes the destination path for users who navigate
 * via "I want to manage my account" rather than the always-available
 * shortcut.
 *
 * Profile editing (name, email, password) is intentionally out of
 * scope for v1: those are Cognito-hosted UIs, and a "Change password"
 * link route can be added when Cognito's hosted-flow URL is wired in.
 * The page existing as a destination matters more than fullness.
 */
export default function SettingsView() {
    const { data: session } = useSession()
    const toast = useToast()
    const [copied, setCopied] = useState(false)
    // Tracked so we can clear it on rapid second clicks (race-free reset of
    // the "Copied" flash) and on unmount (no setState after unmount when the
    // user navigates away within 1.5s of clicking Copy).
    const copiedTimeoutRef = useRef<number | null>(null)

    useEffect(
        () => () => {
            if (copiedTimeoutRef.current !== null) {
                window.clearTimeout(copiedTimeoutRef.current)
            }
        },
        []
    )

    const userName = session?.user?.name ?? ''
    const userEmail = session?.user?.email ?? ''
    const orgId = session?.user?.orgId ?? ''
    const role = session?.user?.role ?? ''

    async function handleCopyOrgId() {
        if (!orgId) return
        try {
            await navigator.clipboard.writeText(orgId)
            setCopied(true)
            toast.success('Copied org ID')
            // Reset the visual checkmark after a moment so a second copy still
            // animates. The toast handles the audible/announce signal.
            // Clear any in-flight timer first so a rapid second click resets
            // the full 1.5s window instead of inheriting the previous one.
            if (copiedTimeoutRef.current !== null) {
                window.clearTimeout(copiedTimeoutRef.current)
            }
            copiedTimeoutRef.current = window.setTimeout(() => {
                setCopied(false)
                copiedTimeoutRef.current = null
            }, 1500)
        } catch {
            toast.error('Failed to copy. Select the value manually.')
        }
    }

    function handleSignOut() {
        signOut({ callbackUrl: '/login' })
    }

    return (
        <div style={{ maxWidth: '720px' }}>
            <header style={{ marginBottom: '2rem' }}>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Settings</h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    Your profile and organisation details. Account changes (password, email) are managed
                    through your authentication provider.
                </p>
            </header>

            <Section title="Profile">
                <Field label="Name" value={userName || '—'} />
                <Field label="Email" value={userEmail || '—'} />
                <p
                    style={{
                        fontSize: '0.8125rem',
                        color: 'var(--text-tertiary)',
                        marginTop: '0.75rem',
                    }}
                >
                    To change your password, sign out and use the &ldquo;Forgot password&rdquo; link on the
                    login page.
                </p>
            </Section>

            <Section title="Organisation">
                {/*
                  Default-deny for unknown role: if the session is missing
                  `role`, we render `member` (the least-privileged label)
                  rather than `admin` or an empty string. Display-only — the
                  backend still gates real privilege checks on the JWT.
                */}
                <Field label="Role" value={role || 'member'} badge />
                <Field
                    label="Organisation ID"
                    value={orgId || '—'}
                    monospace
                    action={
                        orgId ? (
                            <button
                                type="button"
                                onClick={handleCopyOrgId}
                                className="btn btn-ghost btn-sm"
                                aria-label="Copy organisation ID"
                                style={{ fontSize: '0.75rem' }}
                            >
                                {copied ? 'Copied' : 'Copy'}
                            </button>
                        ) : null
                    }
                />
            </Section>

            <Section title="Appearance">
                <p
                    style={{
                        fontSize: '0.8125rem',
                        color: 'var(--text-tertiary)',
                        marginBottom: '0.75rem',
                    }}
                >
                    Choose how sc0red Advisory looks. Print preview always uses the light theme regardless of
                    your selection.
                </p>
                <ThemeToggle />
            </Section>

            <Section title="Session">
                <button
                    type="button"
                    onClick={handleSignOut}
                    className="btn btn-ghost btn-sm"
                    style={{ color: 'var(--risk-critical)' }}
                >
                    Sign out
                </button>
            </Section>
        </div>
    )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <h2
                style={{
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: '1rem',
                }}
            >
                {title}
            </h2>
            {children}
        </section>
    )
}

function Field({
    label,
    value,
    badge,
    monospace,
    action,
}: {
    label: string
    value: string
    badge?: boolean
    monospace?: boolean
    action?: React.ReactNode
}) {
    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '1rem',
                padding: '0.5rem 0',
            }}
        >
            <div style={{ flex: 1, minWidth: 0 }}>
                <div
                    style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-tertiary)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.06em',
                        marginBottom: '0.25rem',
                    }}
                >
                    {label}
                </div>
                {badge ? (
                    <span className="badge badge-blue">{value}</span>
                ) : (
                    <div
                        className="truncate"
                        style={{
                            fontSize: '0.9375rem',
                            color: 'var(--text-primary)',
                            fontFamily: monospace ? 'var(--font-mono)' : undefined,
                        }}
                    >
                        {value}
                    </div>
                )}
            </div>
            {action}
        </div>
    )
}
