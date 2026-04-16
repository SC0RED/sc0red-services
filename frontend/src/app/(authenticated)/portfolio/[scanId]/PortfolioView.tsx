'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import PortfolioProgressStrip from '@/components/scan/PortfolioProgressStrip'
import { getRiskTierLabel, getRiskTier, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { ScanAnalysis, ScanData } from '@/lib/types/api'

const POLL_INTERVAL_MS = 4000

function hasPendingAnalyses(analyses: ScanAnalysis[]): boolean {
    return analyses.some((a) => a.overallRiskScore === null && !a.error)
}

export default function PortfolioView({ scanId, initialScan }: { scanId: string; initialScan: ScanData }) {
    const [scan, setScan] = useState<ScanData>(initialScan)

    useEffect(() => {
        if (!hasPendingAnalyses(scan.analyses) || scan.status === 'complete') return

        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/scan/${scanId}`)
                if (!res.ok) return
                const updated: ScanData = await res.json()
                setScan(updated)
                if (!hasPendingAnalyses(updated.analyses) || updated.status === 'complete') {
                    clearInterval(interval)
                }
            } catch {
                // transient fetch error — keep polling
            }
        }, POLL_INTERVAL_MS)

        return () => clearInterval(interval)
    }, [scanId, scan.analyses, scan.status])

    // Sort by id for stable ordering — DynamoDB BatchGetItem returns items in
    // arbitrary order, so each poll cycle would otherwise shuffle the cards.
    // IDs are UUIDs assigned at confirm time; sorting by them is deterministic.
    const analyses = [...scan.analyses].sort((a, b) => a.id.localeCompare(b.id))
    // totalCompanies from the scan record is the true count (set at confirm time).
    // analyses.length only reflects companies with DynamoDB records (grows as workers pick up messages).
    const totalCompanies = scan.totalCompanies || analyses.length
    const completed = analyses.filter((a) => a.overallRiskScore !== null)
    const avgScore = completed.length
        ? completed.reduce((s, a) => s + Number(a.overallRiskScore), 0) / completed.length
        : 0
    const tierCounts = { critical: 0, high: 0, moderate: 0, low: 0 }
    completed.forEach((a) => {
        if (a.riskTier) tierCounts[a.riskTier as keyof typeof tierCounts]++
    })

    // Show progress strip until scan is complete OR all analyses are resolved
    // (analyzedAt or error). The scan.status can lag behind individual completions
    // because _update_scan_progress runs after each company finishes.
    const resolvedCount = analyses.filter((a) => a.analyzedAt || a.error).length
    const allResolved = resolvedCount >= totalCompanies && totalCompanies > 0
    const isRunning = scan.status !== 'complete' && !allResolved

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
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                    Portfolio Analysis
                </h1>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9375rem' }}>
                    {totalCompanies} companies
                </p>
            </div>

            {/* Progress strip — visible while scan is running */}
            <PortfolioProgressStrip
                completedCount={resolvedCount}
                totalCount={totalCompanies}
                visible={isRunning}
            />

            {/* Stats Row — only after scan completes (partial stats are misleading) */}
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
                        {
                            tier: 'critical',
                            label: 'Critical',
                            color: 'var(--risk-critical)',
                            count: tierCounts.critical,
                        },
                        {
                            tier: 'high',
                            label: 'High Risk',
                            color: 'var(--risk-high)',
                            count: tierCounts.high,
                        },
                        {
                            tier: 'moderate',
                            label: 'Moderate',
                            color: 'var(--risk-moderate)',
                            count: tierCounts.moderate,
                        },
                        { tier: 'low', label: 'Low Risk', color: 'var(--risk-low)', count: tierCounts.low },
                    ].map((s) => (
                        <div key={s.tier} className="card" style={{ padding: '1.25rem' }}>
                            <div style={{ fontSize: '1.625rem', fontWeight: 800, color: s.color }}>
                                {s.count}
                            </div>
                            <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                                {s.label}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Heatmap */}
            <div style={{ marginBottom: '2rem' }}>
                <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>Risk Heatmap</h2>
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                        gap: '0.875rem',
                    }}
                >
                    {analyses.map((a) => {
                        const tier = (a.riskTier ||
                            (a.overallRiskScore ? getRiskTier(Number(a.overallRiskScore)) : null)) as
                            | string
                            | null
                        const color = tier ? TIER_COLORS[tier] : 'var(--text-tertiary)'
                        const isAnalyzed = a.overallRiskScore !== null
                        return (
                            <Link key={a.id} href={`/analysis/${a.id}`} style={{ textDecoration: 'none' }}>
                                <div
                                    className="card"
                                    style={{
                                        padding: '1.125rem',
                                        borderTop: tier
                                            ? `3px solid ${color}`
                                            : '3px solid var(--border-subtle)',
                                        opacity: isAnalyzed ? 1 : 0.6,
                                    }}
                                >
                                    <div
                                        className="truncate"
                                        style={{
                                            fontWeight: 600,
                                            fontSize: '0.9rem',
                                            marginBottom: '0.375rem',
                                        }}
                                    >
                                        {a.companyName || (a.error ? 'Unknown Company' : 'Analyzing...')}
                                    </div>
                                    {a.industry && (
                                        <div
                                            className="truncate"
                                            style={{
                                                fontSize: '0.75rem',
                                                color: 'var(--text-tertiary)',
                                                marginBottom: '0.625rem',
                                            }}
                                        >
                                            {a.industry}
                                        </div>
                                    )}
                                    {isAnalyzed ? (
                                        <div
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'space-between',
                                            }}
                                        >
                                            <span
                                                style={{
                                                    fontSize: '1.5rem',
                                                    fontWeight: 800,
                                                    color,
                                                }}
                                            >
                                                {Number(a.overallRiskScore).toFixed(1)}
                                            </span>
                                            {tier && (
                                                <span
                                                    className={`badge badge-${tier}`}
                                                    style={{ fontSize: '0.7rem' }}
                                                >
                                                    {getRiskTierLabel(tier)}
                                                </span>
                                            )}
                                        </div>
                                    ) : a.error ? (
                                        <span
                                            style={{
                                                display: 'inline-block',
                                                fontSize: '0.7rem',
                                                fontWeight: 600,
                                                padding: '0.2rem 0.5rem',
                                                borderRadius: '4px',
                                                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                                                color: 'var(--risk-critical)',
                                            }}
                                        >
                                            FAILED
                                        </span>
                                    ) : (a.pipelineProgress ?? 0) > 0 ? (
                                        <span
                                            style={{
                                                fontSize: '0.75rem',
                                                color: 'var(--accent-blue)',
                                            }}
                                        >
                                            Analyzing...
                                        </span>
                                    ) : (
                                        <span
                                            style={{
                                                fontSize: '0.75rem',
                                                color: 'var(--text-tertiary)',
                                                opacity: 0.6,
                                            }}
                                        >
                                            Queued
                                        </span>
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
                                {['Company', 'Industry', 'Risk Score', 'Tier', ''].map((h) => (
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
                            {analyses.map((a, i: number) => {
                                const tier = (a.riskTier ||
                                    (a.overallRiskScore ? getRiskTier(Number(a.overallRiskScore)) : null)) as
                                    | string
                                    | null
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
                                            <div style={{ fontWeight: 500 }}>{a.companyName || '—'}</div>
                                            {a.companyUrl && (
                                                <div
                                                    style={{
                                                        fontSize: '0.8125rem',
                                                        color: 'var(--text-tertiary)',
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
                                            {a.overallRiskScore ? (
                                                <span
                                                    style={{
                                                        fontWeight: 700,
                                                        fontSize: '1.1rem',
                                                        color: tier
                                                            ? TIER_COLORS[tier]
                                                            : 'var(--text-secondary)',
                                                    }}
                                                >
                                                    {Number(a.overallRiskScore).toFixed(1)}
                                                </span>
                                            ) : (
                                                <span style={{ color: 'var(--text-tertiary)' }}>—</span>
                                            )}
                                        </td>
                                        <td style={{ padding: '1rem 1.25rem' }}>
                                            {tier && (
                                                <span className={`badge badge-${tier}`}>
                                                    {getRiskTierLabel(tier)}
                                                </span>
                                            )}
                                        </td>
                                        <td style={{ padding: '1rem 1.25rem' }}>
                                            {a.overallRiskScore && (
                                                <Link
                                                    href={`/analysis/${a.id}`}
                                                    className="btn btn-ghost btn-sm"
                                                >
                                                    View Report
                                                </Link>
                                            )}
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </>
    )
}
