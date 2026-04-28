'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import DeleteScanButton from '@/components/DeleteScanButton'
import PortfolioProgressStrip from '@/components/scan/PortfolioProgressStrip'
import { TIER_COLORS } from '@/lib/utils/riskUtils'
import { canDeleteScan } from '@/lib/utils/scanStatus'
import type { ScanAnalysis, ScanData } from '@/lib/types/api'
import PortfolioCard from './PortfolioCard'
import PortfolioRow from './PortfolioRow'

const POLL_INTERVAL_MS = 4000

/**
 * Sort key for stable card ordering. Entries with a numeric `orderIndex`
 * sort by submission order; legacy entries (`null`) fall back to id —
 * matches the pre-change behavior so an in-flight scan deployed across
 * a deploy boundary doesn't crash.
 */
function compareByOrder(a: ScanAnalysis, b: ScanAnalysis): number {
    const ai = a.orderIndex
    const bi = b.orderIndex
    if (ai !== null && bi !== null) return ai - bi
    if (ai !== null) return -1
    if (bi !== null) return 1
    return a.id.localeCompare(b.id)
}

function hasPendingWork(analyses: ScanAnalysis[]): boolean {
    // The unified analyses array always has length === total_companies,
    // so the only thing to check is whether any entry is still in a
    // non-terminal state.
    return analyses.some((a) => a.state === 'pending' || a.state === 'scanning')
}

export default function PortfolioView({ scanId, initialScan }: { scanId: string; initialScan: ScanData }) {
    const [scan, setScan] = useState<ScanData>(initialScan)

    useEffect(() => {
        if (!hasPendingWork(scan.analyses) || scan.status === 'complete') return

        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/scan/${scanId}`)
                if (!res.ok) return
                const updated: ScanData = await res.json()
                setScan(updated)
                if (!hasPendingWork(updated.analyses) || updated.status === 'complete') {
                    clearInterval(interval)
                }
            } catch {
                // transient fetch error — keep polling
            }
        }, POLL_INTERVAL_MS)

        return () => clearInterval(interval)
    }, [scanId, scan.analyses, scan.status])

    // Backend already returns analyses sorted by orderIndex ascending,
    // but apply defensively in case of a future client-side merge.
    const analyses = [...scan.analyses].sort(compareByOrder)
    const totalCompanies = scan.totalCompanies || analyses.length
    const completed = analyses.filter((a) => a.state === 'done')
    const avgScore = completed.length
        ? completed.reduce((s, a) => s + Number(a.overallRiskScore), 0) / completed.length
        : 0
    const tierCounts = { critical: 0, high: 0, moderate: 0, low: 0 }
    completed.forEach((a) => {
        if (a.riskTier) tierCounts[a.riskTier as keyof typeof tierCounts]++
    })

    const resolvedCount = analyses.filter((a) => a.state === 'done' || a.state === 'failed').length
    const isRunning = scan.status !== 'complete' && resolvedCount < totalCompanies

    return (
        <>
            <div style={{ marginBottom: '2rem' }}>
                <div style={{ marginBottom: '0.5rem' }}>
                    <Link
                        href="/dashboard"
                        style={{
                            color: 'var(--text-tertiary)',
                            fontSize: '0.875rem',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                        }}
                    >
                        <svg
                            width="14"
                            height="14"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <path d="m15 18-6-6 6-6" />
                        </svg>
                        Dashboard
                    </Link>
                </div>
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                        gap: '1rem',
                    }}
                >
                    <div>
                        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                            Portfolio Analysis
                        </h1>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                            {totalCompanies} companies
                        </p>
                    </div>
                    {canDeleteScan(scan.status) && (
                        // Bounce to /dashboard on success — `router.refresh()`
                        // would re-fetch this page after its scan was just
                        // tombstoned, which 404s.
                        <DeleteScanButton
                            scanId={scanId}
                            companyCount={totalCompanies}
                            redirectTo="/dashboard"
                            label="Delete portfolio"
                            variant="labelled"
                        />
                    )}
                </div>
            </div>

            <PortfolioProgressStrip
                completedCount={resolvedCount}
                totalCount={totalCompanies}
                visible={isRunning}
            />

            {!isRunning && (
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(5, 1fr)',
                        gap: '1rem',
                        marginBottom: '2rem',
                    }}
                >
                    <div className="card" style={{ padding: '1.25rem' }}>
                        <div style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--accent-blue)' }}>
                            {avgScore.toFixed(1)}
                        </div>
                        <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                            Avg Risk Score
                        </div>
                    </div>
                    {[
                        { tier: 'critical', label: 'Critical', count: tierCounts.critical },
                        { tier: 'high', label: 'High Risk', count: tierCounts.high },
                        { tier: 'moderate', label: 'Moderate', count: tierCounts.moderate },
                        { tier: 'low', label: 'Low Risk', count: tierCounts.low },
                    ].map((s) => (
                        <div key={s.tier} className="card" style={{ padding: '1.25rem' }}>
                            <div
                                style={{
                                    fontSize: '1.625rem',
                                    fontWeight: 800,
                                    color: TIER_COLORS[s.tier] || 'var(--text-secondary)',
                                }}
                            >
                                {s.count}
                            </div>
                            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                                {s.label}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <div style={{ marginBottom: '2rem' }}>
                <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>Risk Heatmap</h2>
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                        gap: '0.875rem',
                    }}
                >
                    {analyses.map((a) => (
                        <PortfolioCard key={a.id} analysis={a} />
                    ))}
                </div>
            </div>

            <div>
                <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>All Companies</h2>
                <div className="card" style={{ overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                {['Company', 'Industry', 'Status / Score', 'Tier', ''].map((h) => (
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
                            {analyses.map((a, i) => (
                                <PortfolioRow key={a.id} analysis={a} isLast={i === analyses.length - 1} />
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </>
    )
}
