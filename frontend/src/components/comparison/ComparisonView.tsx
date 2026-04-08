'use client'

import dynamic from 'next/dynamic'
import Link from 'next/link'

import DashboardSidebar from '@/components/DashboardSidebar'
import ComparisonScoreCards from '@/components/comparison/ComparisonScoreCards'
import ComparisonRiskTable from '@/components/comparison/ComparisonRiskTable'
import { LoadingSpinner } from '@/components/ui'
import type { AnalysisData } from '@/lib/types/api'

const ComparisonRadar = dynamic(() => import('@/components/comparison/ComparisonRadar'), {
    loading: () => (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
            <LoadingSpinner />
        </div>
    ),
    ssr: false,
})

interface ComparisonViewProps {
    analyses: AnalysisData[]
}

export default function ComparisonView({ analyses }: ComparisonViewProps) {
    const opportunityCounts = analyses.map((a) => {
        const opps = a.opportunities ?? []
        return {
            companyName: a.companyName,
            total: opps.length,
            high: opps.filter((o) => o.impact_rating === 'High').length,
            medium: opps.filter((o) => o.impact_rating === 'Medium').length,
            low: opps.filter((o) => o.impact_rating === 'Low').length,
        }
    })

    return (
        <div className="page-layout">
            <DashboardSidebar />
            <main id="main" tabIndex={-1} className="page-content-wide">
                {/* Header */}
                <div style={{ marginBottom: '2rem' }}>
                    <div style={{ marginBottom: '0.5rem' }}>
                        <Link
                            href="/analyses"
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
                            All Analyses
                        </Link>
                    </div>
                    <h1 className="page-title">Comparing {analyses.length} Companies</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        Side-by-side risk profile and opportunity comparison
                    </p>
                </div>

                <ComparisonScoreCards analyses={analyses} />
                <ComparisonRadar analyses={analyses} />
                <ComparisonRiskTable analyses={analyses} />

                {/* Opportunity Summary */}
                <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
                    <div style={{ fontWeight: 600, marginBottom: '1rem', fontSize: '0.9375rem' }}>
                        Opportunities Overview
                    </div>
                    <div
                        style={{
                            display: 'grid',
                            gridTemplateColumns: `repeat(auto-fit, minmax(250px, 1fr))`,
                            gap: '1rem',
                        }}
                    >
                        {opportunityCounts.map((item) => (
                            <div key={item.companyName} style={{ textAlign: 'center' }}>
                                <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>
                                    {item.companyName}
                                </div>
                                <div
                                    style={{
                                        fontSize: '2rem',
                                        fontWeight: 800,
                                        color: 'var(--accent-blue)',
                                        marginBottom: '0.25rem',
                                    }}
                                >
                                    {item.total}
                                </div>
                                <div
                                    style={{
                                        fontSize: '0.75rem',
                                        color: 'var(--text-tertiary)',
                                    }}
                                >
                                    {item.high} High · {item.medium} Medium · {item.low} Low
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </main>
        </div>
    )
}
