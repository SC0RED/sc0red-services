'use client'

import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { signOut, useSession } from 'next-auth/react'

import ActivityPanel from '@/components/ActivityPanel'
import navItems from '@/components/sidebar/navItems'
import { useMobileMenu } from '@/lib/hooks/useMobileMenu'

export default function DashboardSidebar() {
    const pathname = usePathname()
    const { data: session } = useSession()
    const {
        isOpen: mobileOpen,
        open: openMobile,
        close: closeMobile,
        hamburgerRef,
        closeRef,
    } = useMobileMenu()

    return (
        <>
            {/* Mobile hamburger button — visible only at <=768px */}
            <button
                ref={hamburgerRef}
                type="button"
                className="mobile-menu-toggle"
                onClick={openMobile}
                aria-label="Open navigation menu"
            >
                <svg
                    width="22"
                    height="22"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    <line x1="3" y1="6" x2="21" y2="6" />
                    <line x1="3" y1="12" x2="21" y2="12" />
                    <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
            </button>

            {/* Mobile backdrop */}
            {mobileOpen && <div className="mobile-backdrop" onClick={closeMobile} aria-hidden="true" />}

            <aside className={`sidebar ${mobileOpen ? 'sidebar-mobile-open' : ''}`}>
                {/* Mobile close button */}
                <button
                    ref={closeRef}
                    type="button"
                    className="mobile-menu-close"
                    onClick={closeMobile}
                    aria-label="Close navigation menu"
                >
                    <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                </button>

                {/* Logo */}
                <div style={{ padding: '1.25rem 1rem', borderBottom: '1px solid var(--border-subtle)' }}>
                    <Link
                        href="/dashboard"
                        style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}
                    >
                        <div
                            style={{
                                width: '40px',
                                height: '40px',
                                borderRadius: '7px',
                                flexShrink: 0,
                                overflow: 'hidden',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}
                        >
                            <Image
                                src="/sc0red-services-logo.svg"
                                alt="sc0red Services"
                                width={36}
                                height={36}
                                style={{ objectFit: 'contain' }}
                            />
                        </div>
                        <div>
                            <div style={{ fontWeight: 700, fontSize: '0.9375rem', lineHeight: 1 }}>
                                sc0red Services
                            </div>
                            <div
                                style={{
                                    fontSize: '0.6875rem',
                                    color: 'var(--text-tertiary)',
                                    marginTop: '2px',
                                }}
                            >
                                AI Intelligence
                            </div>
                        </div>
                    </Link>
                </div>

                {/* Nav */}
                <nav
                    style={{
                        flex: 1,
                        padding: '0.75rem 0.5rem',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '2px',
                    }}
                >
                    {navItems
                        .filter((item) => !item.adminOnly || session?.user?.role === 'admin')
                        .map((item) => {
                            const active =
                                pathname === item.href ||
                                (item.href !== '/dashboard' && pathname.startsWith(item.href))
                            return (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.625rem',
                                        padding: '0.625rem 0.75rem',
                                        borderRadius: 'var(--radius-md)',
                                        color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                                        background: active ? 'rgba(59,123,246,0.1)' : 'transparent',
                                        borderLeft: active
                                            ? '2px solid var(--accent-blue)'
                                            : '2px solid transparent',
                                        fontSize: '0.875rem',
                                        fontWeight: active ? 600 : 400,
                                        transition: 'all var(--transition-fast)',
                                    }}
                                >
                                    {item.icon}
                                    {item.label}
                                </Link>
                            )
                        })}

                    <div
                        style={{
                            marginTop: '1rem',
                            paddingTop: '1rem',
                            borderTop: '1px solid var(--border-subtle)',
                        }}
                    >
                        <Link
                            href="/scan/new"
                            className="btn btn-primary"
                            style={{
                                width: '100%',
                                justifyContent: 'center',
                                fontSize: '0.8125rem',
                                padding: '0.5rem 1rem',
                            }}
                        >
                            <svg
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2.5"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            >
                                <line x1="12" y1="5" x2="12" y2="19" />
                                <line x1="5" y1="12" x2="19" y2="12" />
                            </svg>
                            New Scan
                        </Link>
                    </div>

                    {/* Activity feed bell + popover. Polls /api/activity
                        every 30s (managed inside the component) and
                        opens above the layout. (Tier 2 §5.) */}
                    <div style={{ marginTop: '0.75rem' }}>
                        <ActivityPanel />
                    </div>
                </nav>

                {/* User footer */}
                <div style={{ padding: '0.75rem 0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
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
            </aside>
        </>
    )
}
