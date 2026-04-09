'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

interface BreadcrumbSegment {
    label: string
    href: string
}

const ROUTE_LABELS: Record<string, string> = {
    dashboard: 'Dashboard',
    analyses: 'Analyses',
    analysis: 'Analysis',
    scan: 'Scan',
    portfolio: 'Portfolio',
    team: 'Team',
    new: 'New Scan',
    compare: 'Compare',
}

export default function Breadcrumbs() {
    const pathname = usePathname()

    if (!pathname || pathname === '/dashboard') return null

    const parts = pathname.split('/').filter(Boolean)
    const segments: BreadcrumbSegment[] = [{ label: 'Dashboard', href: '/dashboard' }]

    let currentPath = ''
    for (const part of parts) {
        currentPath += `/${part}`
        const label = ROUTE_LABELS[part]
        if (label) {
            segments.push({ label, href: currentPath })
        }
    }

    if (segments.length <= 1) return null

    return (
        <nav aria-label="Breadcrumb" style={{ marginBottom: '1rem' }}>
            <ol
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.375rem',
                    listStyle: 'none',
                    padding: 0,
                    margin: 0,
                    fontSize: '0.8125rem',
                    color: 'var(--text-tertiary)',
                }}
            >
                {segments.map((segment, index) => {
                    const isLast = index === segments.length - 1
                    return (
                        <li
                            key={segment.href}
                            style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}
                        >
                            {index > 0 && (
                                <span aria-hidden="true" style={{ opacity: 0.5 }}>
                                    /
                                </span>
                            )}
                            {isLast ? (
                                <span
                                    style={{ color: 'var(--text-secondary)', fontWeight: 500 }}
                                    aria-current="page"
                                >
                                    {segment.label}
                                </span>
                            ) : (
                                <Link href={segment.href} style={{ color: 'var(--text-tertiary)' }}>
                                    {segment.label}
                                </Link>
                            )}
                        </li>
                    )
                })}
            </ol>
        </nav>
    )
}
