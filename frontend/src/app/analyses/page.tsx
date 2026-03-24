import Link from 'next/link'
import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'

import { backendFetch } from '@/lib/api/serverToken'
import { authOptions } from '@/lib/auth/authOptions'
import type { AnalysisItem } from '@/lib/types/api'
import { getRiskTierLabel, TIER_COLORS } from '@/lib/utils/riskUtils'
import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'
import DashboardSidebar from '@/components/DashboardSidebar'

export default async function AnalysesPage() {
    const session = await getServerSession(authOptions)

    if (!session?.user?.orgId) {
        redirect('/login')
    }

    const data = await backendFetch<{ analyses: AnalysisItem[] }>('/api/analyses')
    const analyses = data.analyses

    return (
        <div className="page-layout">
            <DashboardSidebar />
            <main className="page-content">
                <div style={{ marginBottom: '2rem' }}>
                    <h1 className="page-title">All Analyses</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        Browse all completed company risk assessments
                    </p>
                </div>

                {analyses.length === 0 ? (
                    <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
                        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                            No analyses yet. Run your first scan to get started.
                        </p>
                        <Link href="/scan/new" className="btn btn-primary">
                            Start a Scan
                        </Link>
                    </div>
                ) : (
                    <div className="card" style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', minWidth: '860px', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                    {['Company', 'Industry', 'Source', 'Risk Score', 'Tier', 'Date', ''].map(
                                        (h) => (
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
                                        )
                                    )}
                                </tr>
                            </thead>
                            <tbody>
                                {analyses.map((a, i) => {
                                    const tier = a.riskTier ?? ''
                                    return (
                                        <tr
                                            key={a.id}
                                            style={{
                                                borderBottom:
                                                    i < analyses.length - 1
                                                        ? '1px solid var(--border-subtle)'
                                                        : 'none',
                                            }}
                                        >
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <div style={{ fontWeight: 500 }}>{a.companyName}</div>
                                                {a.companyUrl && (
                                                    <div
                                                        style={{
                                                            fontSize: '0.8125rem',
                                                            color: 'var(--text-tertiary)',
                                                            maxWidth: '200px',
                                                            overflow: 'hidden',
                                                            textOverflow: 'ellipsis',
                                                            whiteSpace: 'nowrap',
                                                        }}
                                                    >
                                                        {a.companyUrl}
                                                    </div>
                                                )}
                                            </td>
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    color: 'var(--text-secondary)',
                                                    fontSize: '0.875rem',
                                                }}
                                            >
                                                {a.industry || '—'}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <span
                                                    className={`badge badge-${a.scanType === 'portfolio' ? 'blue' : 'cyan'}`}
                                                    style={{ fontSize: '0.7rem' }}
                                                >
                                                    {a.scanType === 'portfolio' ? 'Portfolio' : 'Standalone'}
                                                </span>
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <span
                                                    style={{
                                                        fontWeight: 700,
                                                        fontSize: '1.1rem',
                                                        color: TIER_COLORS[tier],
                                                    }}
                                                >
                                                    {a.overallRiskScore?.toFixed(1)}
                                                </span>
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                {tier && (
                                                    <span className={`badge badge-${tier}`}>
                                                        {getRiskTierLabel(tier)}
                                                    </span>
                                                )}
                                            </td>
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    color: 'var(--text-tertiary)',
                                                    fontSize: '0.8125rem',
                                                    whiteSpace: 'nowrap',
                                                }}
                                            >
                                                {a.analyzedAt
                                                    ? new Date(a.analyzedAt).toLocaleDateString()
                                                    : '—'}
                                            </td>
                                            <td
                                                style={{
                                                    padding: '1rem 1.25rem',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '0.25rem',
                                                }}
                                            >
                                                <Link
                                                    href={`/analysis/${a.id}`}
                                                    className="btn btn-ghost btn-sm"
                                                >
                                                    View
                                                </Link>
                                                <DeleteAnalysisButton
                                                    analysisId={a.id}
                                                    companyName={a.companyName}
                                                />
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </main>
        </div>
    )
}
