import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/authOptions'
import { getDb, initializeDb } from '@/lib/db/client'
import { getRiskTierLabel, getRiskTier } from '@/lib/utils/riskUtils'
import Link from 'next/link'
import DashboardSidebar from '@/components/DashboardSidebar'

export default async function PortfolioPage({ params }: { params: { scanId: string } }) {
    const session = await getServerSession(authOptions)
    const orgId = (session?.user as any)?.orgId

    if (!session || !orgId) {
        const { redirect } = await import('next/navigation')
        redirect('/login')
    }

    await initializeDb()
    const db = getDb()

    const scanResult = await db.execute({
        sql: `SELECT * FROM scans WHERE id = ? AND org_id = ?`,
        args: [params.scanId, orgId],
    })
    const scan = scanResult.rows[0] as any
    if (!scan) return <div style={{ padding: '2rem', color: 'var(--risk-critical)' }}>Scan not found</div>

    const analysesResult = await db.execute({
        sql: `SELECT ca.* FROM company_analyses ca WHERE ca.scan_id = ? ORDER BY ca.overall_risk_score DESC`,
        args: [params.scanId],
    })
    const analyses = analysesResult.rows as any[]

    const completed = analyses.filter((a: any) => a.overall_risk_score !== null)
    const avgScore = completed.length ? completed.reduce((s: number, a: any) => s + Number(a.overall_risk_score), 0) / completed.length : 0
    const tierCounts = { critical: 0, high: 0, moderate: 0, low: 0 }
    completed.forEach((a: any) => { if (a.risk_tier) tierCounts[a.risk_tier as keyof typeof tierCounts]++ })

    const tierColors: Record<string, string> = { low: 'var(--risk-low)', moderate: 'var(--risk-moderate)', high: 'var(--risk-high)', critical: 'var(--risk-critical)' }

    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            <DashboardSidebar />
            <main style={{ flex: 1, marginLeft: 'var(--sidebar-width)', padding: '2rem', maxWidth: '1200px' }}>

                <div style={{ marginBottom: '2rem' }}>
                    <div style={{ marginBottom: '0.5rem' }}>
                        <Link href="/dashboard" style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6" /></svg>
                            Dashboard
                        </Link>
                    </div>
                    <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Portfolio Analysis</h1>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                        {scan.source_url} · {analyses.length} companies · Scanned {new Date(scan.created_at as string).toLocaleDateString()}
                    </p>
                </div>

                {/* Stats Row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
                    <div className="card" style={{ padding: '1.25rem' }}>
                        <div style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--accent-blue)' }}>{avgScore.toFixed(1)}</div>
                        <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Avg Risk Score</div>
                    </div>
                    {[
                        { tier: 'critical', label: 'Critical', color: 'var(--risk-critical)', count: tierCounts.critical },
                        { tier: 'high', label: 'High Risk', color: 'var(--risk-high)', count: tierCounts.high },
                        { tier: 'moderate', label: 'Moderate', color: 'var(--risk-moderate)', count: tierCounts.moderate },
                        { tier: 'low', label: 'Low Risk', color: 'var(--risk-low)', count: tierCounts.low },
                    ].map(s => (
                        <div key={s.tier} className="card" style={{ padding: '1.25rem' }}>
                            <div style={{ fontSize: '1.625rem', fontWeight: 800, color: s.color }}>{s.count}</div>
                            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{s.label}</div>
                        </div>
                    ))}
                </div>

                {/* Heatmap */}
                <div style={{ marginBottom: '2rem' }}>
                    <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>Risk Heatmap</h2>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.875rem' }}>
                        {analyses.map((a: any) => {
                            const tier = (a.risk_tier || (a.overall_risk_score ? getRiskTier(Number(a.overall_risk_score)) : null)) as string | null
                            const color = tier ? tierColors[tier] : 'var(--text-tertiary)'
                            const isAnalyzed = a.overall_risk_score !== null
                            return (
                                <Link key={a.id as string} href={`/analysis/${a.id as string}`} style={{ textDecoration: 'none' }}>
                                    <div className="card" style={{ padding: '1.125rem', borderTop: tier ? `3px solid ${color}` : '3px solid var(--border-subtle)', opacity: isAnalyzed ? 1 : 0.6 }}>
                                        <div className="truncate" style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.375rem' }}>{(a.company_name as string) || 'Analyzing...'}</div>
                                        {a.industry && <div className="truncate" style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginBottom: '0.625rem' }}>{a.industry as string}</div>}
                                        {isAnalyzed ? (
                                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                                <span style={{ fontSize: '1.5rem', fontWeight: 800, color }}>{(Number(a.overall_risk_score)).toFixed(1)}</span>
                                                {tier && <span className={`badge badge-${tier}`} style={{ fontSize: '0.7rem' }}>{getRiskTierLabel(tier)}</span>}
                                            </div>
                                        ) : (
                                            a.error ? <span style={{ fontSize: '0.75rem', color: 'var(--risk-critical)' }}>Analysis failed</span>
                                                : <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Analyzing...</span>
                                        )}
                                    </div>
                                </Link>
                            )
                        })}
                    </div>
                </div>

                {/* Table */}
                <div>
                    <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>All Companies</h2>
                    <div className="card" style={{ overflow: 'hidden' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                    {['Company', 'Industry', 'Risk Score', 'Tier', ''].map(h => (
                                        <th key={h} style={{ padding: '0.875rem 1.25rem', textAlign: 'left', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {analyses.map((a: any, i: number) => {
                                    const tier = (a.risk_tier || (a.overall_risk_score ? getRiskTier(Number(a.overall_risk_score)) : null)) as string | null
                                    return (
                                        <tr key={a.id as string} style={{ borderBottom: i < analyses.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <div style={{ fontWeight: 500 }}>{a.company_name as string || '—'}</div>
                                                {a.company_url && <div style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>{a.company_url as string}</div>}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{(a.industry as string) || '—'}</td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                {a.overall_risk_score ? (
                                                    <span style={{ fontWeight: 700, fontSize: '1.1rem', color: tier ? tierColors[tier] : 'var(--text-secondary)' }}>
                                                        {Number(a.overall_risk_score).toFixed(1)}
                                                    </span>
                                                ) : <span style={{ color: 'var(--text-tertiary)' }}>—</span>}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                {tier && <span className={`badge badge-${tier}`}>{getRiskTierLabel(tier)}</span>}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                {a.overall_risk_score && (
                                                    <Link href={`/analysis/${a.id as string}`} className="btn btn-ghost btn-sm">View Report</Link>
                                                )}
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </main>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    )
}
