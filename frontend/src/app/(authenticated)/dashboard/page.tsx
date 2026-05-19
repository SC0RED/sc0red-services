import Link from 'next/link'
import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import type { Metadata } from 'next'

import { backendFetch } from '@/lib/api/serverToken'
import { authOptions } from '@/lib/auth/authOptions'
import type { DashboardData } from '@/lib/types/api'
import { TIER_COLORS, TIER_BG_COLORS } from '@/lib/utils/riskUtils'
import DeleteScanButton from '@/components/DeleteScanButton'
import { EmptyState } from '@/components/ui'
import RelativeTime from '@/components/ui/RelativeTime'
import { canDeleteScan, displayedCompanyCount } from '@/lib/utils/scanStatus'

export const metadata: Metadata = { title: 'Dashboard — sc0red Advisory' }

export default async function DashboardPage() {
    const session = await getServerSession(authOptions)

    if (!session?.user?.orgId) {
        redirect('/login')
    }

    const data = await backendFetch<DashboardData>('/api/dashboard')

    const userName = session.user.name?.split(' ')?.[0] ?? 'there'

    const stats = [
        { label: 'Companies Analyzed', value: data.totalAnalyses, color: 'var(--accent-blue)' },
        {
            label: 'Avg Risk Score',
            value: data.avgRiskScore > 0 ? data.avgRiskScore.toFixed(1) : '—',
            color: 'var(--accent-cyan)',
        },
        { label: 'Critical Risks', value: data.criticalCount, color: 'var(--risk-critical)' },
        { label: 'Total Scans', value: data.scanCount, color: 'var(--text-secondary)' },
    ]

    return (
        <>
            <div style={{ marginBottom: '2rem' }}>
                <h1 className="page-title">
                    Good{' '}
                    {(() => {
                        const hour = new Date().getHours()
                        return hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening'
                    })()}
                    , {userName} 👋
                </h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    Here&apos;s your AI risk intelligence overview
                </p>
            </div>

            {/* Stats */}
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '1rem',
                    marginBottom: '2.5rem',
                }}
            >
                {stats.map((s) => (
                    <div key={s.label} className="card" style={{ padding: '1.5rem' }}>
                        <div
                            style={{
                                fontSize: '1.75rem',
                                fontWeight: 800,
                                color: s.color,
                                marginBottom: '0.25rem',
                            }}
                        >
                            {s.value}
                        </div>
                        <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{s.label}</div>
                    </div>
                ))}
            </div>

            {data.totalAnalyses === 0 ? (
                <EmptyState
                    icon="🔍"
                    title="Run your first analysis"
                    description="Analyze a PE portfolio or single company to identify AI-driven risks and opportunities."
                    action={
                        <div className="flex gap-md justify-center">
                            <Link href="/scan/new?type=portfolio" className="btn btn-primary">
                                <svg
                                    width="16"
                                    height="16"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                >
                                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                                    <circle cx="9" cy="7" r="4" />
                                    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                                    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                                </svg>
                                Scan PE Portfolio
                            </Link>
                            <Link href="/scan/new?type=standalone" className="btn btn-secondary">
                                Single Company
                            </Link>
                        </div>
                    }
                />
            ) : (
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '1.5rem',
                        alignItems: 'start',
                    }}
                >
                    {/* Recent Company Analyses */}
                    <div style={{ gridColumn: '1 / -1' }}>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: '1rem',
                            }}
                        >
                            <h2 style={{ fontWeight: 700, fontSize: '1.125rem' }}>Recent Analyses</h2>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <Link href="/analyses" className="btn btn-ghost btn-sm">
                                    View All
                                </Link>
                                <Link href="/scan/new" className="btn btn-primary btn-sm">
                                    + New Scan
                                </Link>
                            </div>
                        </div>
                        <div className="card" style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '700px' }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                        {['Company', 'Risk Score', 'Tier', 'Source', 'Date', ''].map((h) => (
                                            <th
                                                key={h}
                                                style={{
                                                    padding: '0.875rem 1.25rem',
                                                    textAlign: 'left',
                                                    fontSize: '0.8125rem',
                                                    fontWeight: 600,
                                                    color: 'var(--text-secondary)',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.06em',
                                                }}
                                            >
                                                {h}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.recentAnalyses.map((analysis, i) => {
                                        const analysisTier = analysis.riskTier || 'moderate'
                                        const score = Number(analysis.overallRiskScore || 0)
                                        return (
                                            <tr
                                                key={analysis.id}
                                                style={{
                                                    borderBottom:
                                                        i < data.recentAnalyses.length - 1
                                                            ? '1px solid var(--border-subtle)'
                                                            : 'none',
                                                }}
                                            >
                                                <td style={{ padding: '1rem 1.25rem' }}>
                                                    <div
                                                        style={{
                                                            fontWeight: 600,
                                                            fontSize: '0.9rem',
                                                        }}
                                                    >
                                                        {analysis.companyName || 'Unknown'}
                                                    </div>
                                                    <div
                                                        style={{
                                                            fontSize: '0.75rem',
                                                            color: 'var(--text-tertiary)',
                                                        }}
                                                    >
                                                        {analysis.companyUrl}
                                                    </div>
                                                </td>
                                                <td style={{ padding: '1rem 1.25rem' }}>
                                                    <span
                                                        style={{
                                                            fontSize: '1.125rem',
                                                            fontWeight: 700,
                                                            color:
                                                                TIER_COLORS[analysisTier] ||
                                                                'var(--text-primary)',
                                                        }}
                                                    >
                                                        {score.toFixed(1)}
                                                    </span>
                                                </td>
                                                <td style={{ padding: '1rem 1.25rem' }}>
                                                    <span
                                                        style={{
                                                            display: 'inline-block',
                                                            padding: '0.2rem 0.65rem',
                                                            borderRadius: '999px',
                                                            fontSize: '0.75rem',
                                                            fontWeight: 600,
                                                            textTransform: 'capitalize',
                                                            background:
                                                                TIER_BG_COLORS[analysisTier] ||
                                                                'var(--bg-surface-2)',
                                                            color:
                                                                TIER_COLORS[analysisTier] ||
                                                                'var(--text-primary)',
                                                        }}
                                                    >
                                                        {analysisTier}
                                                    </span>
                                                </td>
                                                <td style={{ padding: '1rem 1.25rem' }}>
                                                    <span
                                                        className={`badge badge-${analysis.scanType === 'portfolio' ? 'blue' : 'cyan'}`}
                                                    >
                                                        {analysis.scanType}
                                                    </span>
                                                </td>
                                                <td
                                                    style={{
                                                        padding: '1rem 1.25rem',
                                                        color: 'var(--text-tertiary)',
                                                        fontSize: '0.8125rem',
                                                        whiteSpace: 'nowrap',
                                                    }}
                                                >
                                                    <RelativeTime value={analysis.analyzedAt} />
                                                </td>
                                                <td style={{ padding: '1rem 1.25rem' }}>
                                                    <Link
                                                        href={`/analysis/${analysis.id}`}
                                                        className="btn btn-ghost btn-sm"
                                                    >
                                                        View Report
                                                    </Link>
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Recent Scans */}
                    <div style={{ gridColumn: '1 / -1' }}>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: '1rem',
                            }}
                        >
                            <h2 style={{ fontWeight: 700, fontSize: '1.125rem' }}>Recent Scans</h2>
                        </div>
                        <div className="card" style={{ overflowX: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '700px' }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                        {['Source', 'Type', 'Status', 'Companies', 'Date', ''].map((h) => (
                                            <th
                                                key={h}
                                                style={{
                                                    padding: '0.875rem 1.25rem',
                                                    textAlign: 'left',
                                                    fontSize: '0.8125rem',
                                                    fontWeight: 600,
                                                    color: 'var(--text-secondary)',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.06em',
                                                }}
                                            >
                                                {h}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.recentScans.map((scan, i) => (
                                        <tr
                                            key={scan.id}
                                            style={{
                                                borderBottom:
                                                    i < data.recentScans.length - 1
                                                        ? '1px solid var(--border-subtle)'
                                                        : 'none',
                                            }}
                                        >
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    maxWidth: '280px',
                                                }}
                                            >
                                                <div className="truncate" style={{ fontSize: '0.875rem' }}>
                                                    {scan.sourceUrl}
                                                </div>
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <span
                                                    className={`badge badge-${scan.type === 'portfolio' ? 'blue' : 'cyan'}`}
                                                >
                                                    {scan.type}
                                                </span>
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                {scan.status === 'complete' ? (
                                                    <span className="badge badge-low">Complete</span>
                                                ) : scan.status === 'failed' ? (
                                                    <span className="badge badge-critical">Failed</span>
                                                ) : (
                                                    <span className="badge badge-moderate">
                                                        {scan.progress}%
                                                    </span>
                                                )}
                                            </td>
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    color: 'var(--text-secondary)',
                                                    fontSize: '0.875rem',
                                                }}
                                            >
                                                {displayedCompanyCount(scan)}
                                            </td>
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    color: 'var(--text-tertiary)',
                                                    fontSize: '0.8125rem',
                                                    whiteSpace: 'nowrap',
                                                }}
                                            >
                                                <RelativeTime value={scan.createdAt} />
                                            </td>
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '0.25rem',
                                                }}
                                            >
                                                {scan.type === 'portfolio' ? (
                                                    <Link
                                                        href={`/portfolio/${scan.id}`}
                                                        className="btn btn-ghost btn-sm"
                                                    >
                                                        View Portfolio
                                                    </Link>
                                                ) : scan.status === 'complete' ? (
                                                    <Link href="/analyses" className="btn btn-ghost btn-sm">
                                                        View
                                                    </Link>
                                                ) : null}
                                                {canDeleteScan(scan.status) && (
                                                    <DeleteScanButton
                                                        scanId={scan.id}
                                                        // Shared helper — keeps the cascade-message
                                                        // scope and the Companies-cell count from
                                                        // drifting (the bug this fix is closing).
                                                        companyCount={displayedCompanyCount(scan)}
                                                    />
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
