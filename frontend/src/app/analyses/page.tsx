import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth/authOptions'
import { getDb, initializeDb } from '@/lib/db/client'
import { getRiskTierLabel } from '@/lib/utils/riskUtils'
import Link from 'next/link'
import DashboardSidebar from '@/components/DashboardSidebar'
import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'

export default async function AnalysesPage() {
    const session = await getServerSession(authOptions)
    const orgId = (session?.user as any)?.orgId

    if (!session || !orgId) {
        const { redirect } = await import('next/navigation')
        redirect('/login')
    }

    await initializeDb()
    const db = getDb()

    const result = await db.execute({
        sql: `SELECT ca.id, ca.company_name, ca.company_url, ca.industry, ca.overall_risk_score, ca.risk_tier, ca.analyzed_at, s.type as scan_type FROM company_analyses ca JOIN scans s ON s.id = ca.scan_id WHERE s.org_id = ? AND ca.overall_risk_score IS NOT NULL ORDER BY ca.analyzed_at DESC LIMIT 50`,
        args: [orgId],
    })
    const analyses = result.rows as any[]

    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            <DashboardSidebar />
            <main style={{ flex: 1, marginLeft: 'var(--sidebar-width)', padding: '2rem', maxWidth: '1100px' }}>
                <div style={{ marginBottom: '2rem' }}>
                    <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>All Analyses</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>Browse all completed company risk assessments</p>
                </div>

                {analyses.length === 0 ? (
                    <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
                        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>No analyses yet. Run your first scan to get started.</p>
                        <Link href="/scan/new" className="btn btn-primary">Start a Scan</Link>
                    </div>
                ) : (
                    <div className="card" style={{ overflow: 'hidden' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                    {['Company', 'Industry', 'Source', 'Risk Score', 'Tier', 'Date', ''].map(h => (
                                        <th key={h} style={{ padding: '0.875rem 1.25rem', textAlign: 'left', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {analyses.map((a: any, i: number) => {
                                    const tier = a.risk_tier as string
                                    const tierColors: Record<string, string> = { low: 'var(--risk-low)', moderate: 'var(--risk-moderate)', high: 'var(--risk-high)', critical: 'var(--risk-critical)' }
                                    return (
                                        <tr key={a.id as string} style={{ borderBottom: i < analyses.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <div style={{ fontWeight: 500 }}>{a.company_name as string}</div>
                                                {a.company_url && <div style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.company_url as string}</div>}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{(a.industry as string) || '—'}</td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <span className={`badge badge-${a.scan_type === 'portfolio' ? 'blue' : 'cyan'}`} style={{ fontSize: '0.7rem' }}>
                                                    {a.scan_type === 'portfolio' ? 'Portfolio' : 'Standalone'}
                                                </span>
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                <span style={{ fontWeight: 700, fontSize: '1.1rem', color: tierColors[tier] }}>
                                                    {(a.overall_risk_score as number)?.toFixed(1)}
                                                </span>
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem' }}>
                                                {tier && <span className={`badge badge-${tier}`}>{getRiskTierLabel(tier)}</span>}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem', color: 'var(--text-tertiary)', fontSize: '0.8125rem', whiteSpace: 'nowrap' }}>
                                                {new Date(a.analyzed_at as string).toLocaleDateString()}
                                            </td>
                                            <td style={{ padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                                <Link href={`/analysis/${a.id as string}`} className="btn btn-ghost btn-sm">View</Link>
                                                <DeleteAnalysisButton analysisId={a.id as string} companyName={a.company_name as string} />
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
