'use client'

import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useSession } from 'next-auth/react'
import { useEffect, useState } from 'react'

import ActivityPanel from '@/components/ActivityPanel'
import navItems from '@/components/sidebar/navItems'
import SidebarFooter from '@/components/sidebar/SidebarFooter'
import { useMobileMenu } from '@/lib/hooks/useMobileMenu'

// One-time "New" awareness pill on the Connect entry: shown until the user has
// visited /connect once (per-device, via localStorage). A muted nudge that
// doesn't nag — it clears on first visit and never returns on this device.
export const CONNECT_SEEN_KEY = 'sc0red-services.connect-seen'

// Per-env marketing site root, baked in at build time by the Amplify
// branch env var (see infrastructure/stacks/sc0red_services_stack.py).
// Mirrors the constant used in app/page.tsx and app/login/page.tsx so
// every "back to marketing" link points at the right environment. Falls
// back to prod for local dev / preview builds where the var isn't set.
const MARKETING_URL = process.env.NEXT_PUBLIC_MARKETING_URL ?? 'https://www.sc0red.com'

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

    // Show the Connect "New" pill until the user's first visit to /connect.
    const [connectSeen, setConnectSeen] = useState(true) // assume seen until proven otherwise (no flash)
    useEffect(() => {
        setConnectSeen(localStorage.getItem(CONNECT_SEEN_KEY) === '1')
    }, [])
    useEffect(() => {
        if (pathname.startsWith('/connect') && !connectSeen) {
            localStorage.setItem(CONNECT_SEEN_KEY, '1')
            setConnectSeen(true)
        }
    }, [pathname, connectSeen])

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

                {/*
                 * Logo block — links to the marketing homepage rather than
                 * `/dashboard`. The Dashboard nav item right below covers
                 * the in-app destination, so the brand block follows the
                 * web convention of "wordmark → homepage" (Diagnostic Tool
                 * Feedback #2). Uses a plain `<a>` not `<Link>` because
                 * the target is external to the Next.js app router.
                 *
                 * Opens in a NEW TAB (``target="_blank"``) so an
                 * accidental click on the logo doesn't tear the user out
                 * of their in-progress analysis. Phase 11 of
                 * ``redesign-analysis-visuals`` corrected the prior
                 * same-tab behaviour after Zack reported losing a session
                 * mid-review.
                 */}
                <div style={{ padding: '1.25rem 1rem', borderBottom: '1px solid var(--border-subtle)' }}>
                    <a
                        href={MARKETING_URL}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.625rem',
                            textDecoration: 'none',
                            color: 'inherit',
                        }}
                        aria-label="sc0red Services — back to sc0red.com (opens in new tab)"
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
                    </a>
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
                                    <span style={{ flex: 1 }}>{item.label}</span>
                                    {item.href === '/connect' && !connectSeen && (
                                        <span
                                            style={{
                                                fontSize: '0.625rem',
                                                fontWeight: 600,
                                                textTransform: 'uppercase',
                                                letterSpacing: '0.04em',
                                                padding: '0.05rem 0.35rem',
                                                borderRadius: '999px',
                                                color: 'var(--accent-blue)',
                                                background: 'rgba(59,123,246,0.12)',
                                            }}
                                        >
                                            New
                                        </span>
                                    )}
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

                <SidebarFooter />
            </aside>
        </>
    )
}
