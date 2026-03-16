'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import dynamic from 'next/dynamic'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts'

import RiskBadge from '@/components/RiskBadge'
import DeleteAnalysisButton from '@/components/DeleteAnalysisButton'
import DashboardSidebar from '@/components/DashboardSidebar'
import DocumentUpload from '@/components/DocumentUpload'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import { getRiskTier, RISK_CATEGORIES } from '@/lib/utils/riskUtils'
import type { AnalysisData, DocumentInfo, Opportunity, RiskScore } from '@/lib/types/api'

const EbitdaTree = dynamic(() => import('@/components/EbitdaTree'), { ssr: false })

function ImpactBadge({ impact }: { impact: string }) {
    const colorMap: Record<string, string> = { High: 'low', Medium: 'moderate', Low: 'neutral' }
    return <span className={`badge badge-${colorMap[impact] || 'neutral'}`}>{impact} Impact</span>
}

function TimelineBadge({ timeline }: { timeline: string }) {
    return (
        <span className="badge badge-blue" style={{ fontSize: '0.7rem' }}>
            {timeline}
        </span>
    )
}

const CAT_LABELS: Record<string, string> = {
    competitive_displacement: 'Competitive Displ.',
    technology_obsolescence: 'Tech Obsolescence',
    talent_workforce: 'Talent & Workforce',
    margin_compression: 'Margin Compression',
    customer_behavior: 'Customer Behavior',
    regulatory_compliance: 'Regulatory',
    supply_chain: 'Supply Chain',
    data_ip: 'Data & IP',
}

const TIER_COLORS: Record<string, string> = {
    low: 'var(--risk-low)',
    moderate: 'var(--risk-moderate)',
    high: 'var(--risk-high)',
    critical: 'var(--risk-critical)',
}

export default function AnalysisDetail({ data, analysisId }: { data: AnalysisData; analysisId: string }) {
    const router = useRouter()
    const [activeOppCat, setActiveOppCat] = useState<string>('All')
    const [activeLever, setActiveLever] = useState<string>('All')
    const [expandedRisk, setExpandedRisk] = useState<string | null>(null)
    const [expandedOpp, setExpandedOpp] = useState<string | null>(null)
    const [documents, setDocuments] = useState<DocumentInfo[]>(data.documents ?? [])
    const [reanalyzing, setReanalyzing] = useState(false)
    const [documentError, setDocumentError] = useState<string | null>(null)

    const handleDocumentsChange = useCallback(async () => {
        setDocumentError(null)
        try {
            const response = await fetch(`/api/analysis/${analysisId}`)
            if (!response.ok) throw new Error('Failed to refresh documents')
            const updated = (await response.json()) as AnalysisData
            setDocuments(updated.documents ?? [])
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : 'Failed to refresh documents'
            setDocumentError(message)
        }
    }, [analysisId])

    const abortControllerRef = useRef<AbortController | null>(null)

    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort()
        }
    }, [])

    const handleReanalyze = useCallback(async () => {
        setReanalyzing(true)
        setDocumentError(null)
        const controller = new AbortController()
        abortControllerRef.current = controller
        try {
            const response = await fetch(`/api/analysis/${analysisId}/reanalyze`, {
                method: 'POST',
                signal: controller.signal,
            })
            if (!response.ok) throw new Error('Re-analysis failed')

            // Poll until analyzedAt changes (indicates pipeline completed) or timeout (2 min)
            const maxAttempts = 40
            const intervalMs = 3000
            const originalAnalyzedAt = data.analyzedAt
            let consecutiveErrors = 0

            for (let attempt = 0; attempt < maxAttempts; attempt++) {
                await new Promise((resolve) => setTimeout(resolve, intervalMs))
                if (controller.signal.aborted) return
                try {
                    const pollResponse = await fetch(`/api/analysis/${analysisId}`, {
                        signal: controller.signal,
                    })
                    if (!pollResponse.ok) {
                        consecutiveErrors++
                        if (consecutiveErrors >= 3) throw new Error('Polling failed')
                        continue
                    }
                    consecutiveErrors = 0
                    const updated = (await pollResponse.json()) as AnalysisData
                    if (updated.analyzedAt && updated.analyzedAt !== originalAnalyzedAt) {
                        router.refresh()
                        return
                    }
                } catch (error: unknown) {
                    if (error instanceof DOMException && error.name === 'AbortError') return
                    throw error
                }
            }

            // Timeout — refresh anyway to show whatever state we have
            router.refresh()
        } catch (error: unknown) {
            if (error instanceof DOMException && error.name === 'AbortError') return
            const message = error instanceof Error ? error.message : 'Re-analysis failed'
            setDocumentError(message)
        } finally {
            setReanalyzing(false)
            abortControllerRef.current = null
        }
    }, [analysisId, data.analyzedAt, router])

    const riskScores = data.riskScores ?? []
    const opportunities = data.opportunities ?? []

    const tier = data.riskTier || getRiskTier(data.overallRiskScore ?? 0)
    const tierColor = TIER_COLORS[tier] || 'var(--text-secondary)'

    const radarData = RISK_CATEGORIES.map((cat) => {
        const rs = riskScores.find((r) => r.category === cat.id)
        return { category: CAT_LABELS[cat.id] ?? cat.name, score: rs?.score ?? 0, fullMark: 10 }
    })

    const uniqueCategories = opportunities
        .map((o) => o.strategic_category)
        .filter((cat, index, arr) => arr.indexOf(cat) === index)
    const oppCategories = ['All', ...uniqueCategories]
    const filteredOpps = opportunities.filter((o) => {
        if (activeOppCat !== 'All' && o.strategic_category !== activeOppCat) return false
        if (activeLever !== 'All' && o.value_lever !== activeLever) return false
        return true
    })

    const hasValueLevers = opportunities.some((o) => o.value_lever)

    const leverSummary = hasValueLevers
        ? (['Revenue Side', 'Cost Side', 'Both'] as const).map((lever) => ({
              lever,
              count: opportunities.filter((o) => o.value_lever === lever).length,
          }))
        : []

    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            <DashboardSidebar />
            <main
                style={{
                    flex: 1,
                    marginLeft: 'var(--sidebar-width)',
                    maxWidth: '1100px',
                    margin: '0 auto 0 var(--sidebar-width)',
                    padding: '2rem',
                }}
            >
                {/* Header */}
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: '2rem',
                        flexWrap: 'wrap',
                        gap: '1rem',
                    }}
                >
                    <div>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.75rem',
                                marginBottom: '0.5rem',
                            }}
                        >
                            <Link
                                href="/dashboard"
                                style={{
                                    color: 'var(--text-tertiary)',
                                    fontSize: '0.875rem',
                                    display: 'flex',
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
                        <h1 style={{ fontSize: '1.625rem', fontWeight: 700, marginBottom: '0.375rem' }}>
                            {data.companyName}
                        </h1>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.75rem',
                                flexWrap: 'wrap',
                            }}
                        >
                            <RiskBadge tier={tier} />
                            {data.industry && <span className="badge badge-neutral">{data.industry}</span>}
                            {data.companyUrl && (
                                <a
                                    href={data.companyUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                        color: 'var(--text-tertiary)',
                                        fontSize: '0.8125rem',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '0.25rem',
                                    }}
                                >
                                    <svg
                                        width="13"
                                        height="13"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                    >
                                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                        <polyline points="15 3 21 3 21 9" />
                                        <line x1="10" y1="14" x2="21" y2="3" />
                                    </svg>
                                    {data.companyUrl}
                                </a>
                            )}
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <Link
                            href={`/api/export/pdf/${analysisId}`}
                            target="_blank"
                            className="btn btn-secondary"
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
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                <polyline points="7 10 12 15 17 10" />
                                <line x1="12" y1="15" x2="12" y2="3" />
                            </svg>
                            Export PDF
                        </Link>
                        <DeleteAnalysisButton
                            analysisId={analysisId}
                            companyName={data.companyName}
                            variant="button"
                            redirectTo="/analyses"
                        />
                    </div>
                </div>

                {/* Score + Radar */}
                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: '280px 1fr',
                        gap: '1.25rem',
                        marginBottom: '1.5rem',
                    }}
                >
                    {/* Score Card */}
                    <div
                        className="card"
                        style={{
                            padding: '2rem',
                            textAlign: 'center',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                        }}
                    >
                        <div
                            style={{
                                fontSize: '0.8125rem',
                                color: 'var(--text-secondary)',
                                fontWeight: 500,
                                marginBottom: '0.75rem',
                                textTransform: 'uppercase',
                                letterSpacing: '0.08em',
                            }}
                        >
                            Overall AI Risk Score
                        </div>
                        <div
                            style={{
                                width: '120px',
                                height: '120px',
                                borderRadius: '50%',
                                border: `6px solid ${tierColor}`,
                                boxShadow: `0 0 40px ${tierColor}40`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                marginBottom: '1.25rem',
                            }}
                        >
                            <span
                                style={{
                                    fontSize: '2.5rem',
                                    fontWeight: 800,
                                    color: tierColor,
                                    lineHeight: 1,
                                }}
                            >
                                {data.overallRiskScore?.toFixed(1) || '—'}
                            </span>
                        </div>
                        <RiskBadge tier={tier} />
                        {data.analysisSummary && (
                            <p
                                style={{
                                    marginTop: '1rem',
                                    fontSize: '0.8125rem',
                                    color: 'var(--text-secondary)',
                                    lineHeight: 1.6,
                                    textAlign: 'left',
                                }}
                            >
                                {data.analysisSummary}
                            </p>
                        )}
                    </div>

                    {/* Radar */}
                    <div className="card" style={{ padding: '1.5rem' }}>
                        <div style={{ fontWeight: 600, marginBottom: '1rem', fontSize: '0.9375rem' }}>
                            Risk Dimensions
                        </div>
                        <ResponsiveContainer width="100%" height={280}>
                            <RadarChart data={radarData}>
                                <PolarGrid stroke="var(--border)" />
                                <PolarAngleAxis
                                    dataKey="category"
                                    tick={{ fill: 'var(--text-primary)', fontSize: 11, fontWeight: 500 }}
                                />
                                <Radar
                                    name="Risk"
                                    dataKey="score"
                                    stroke={tierColor}
                                    fill={tierColor}
                                    fillOpacity={0.12}
                                    strokeWidth={2}
                                />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Top Actions Callout */}
                {data.topActions && data.topActions.length > 0 && (
                    <div
                        className="card"
                        style={{
                            padding: '1.25rem 1.5rem',
                            marginBottom: '1.5rem',
                            borderColor: 'rgba(59,123,246,0.3)',
                            background: 'rgba(59,123,246,0.04)',
                        }}
                    >
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.625rem',
                                marginBottom: '0.875rem',
                            }}
                        >
                            <svg
                                width="17"
                                height="17"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="var(--accent-blue)"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                            >
                                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                            </svg>
                            <span
                                style={{
                                    fontWeight: 700,
                                    color: 'var(--accent-blue)',
                                    fontSize: '0.9rem',
                                }}
                            >
                                Top 3 Immediate Actions
                            </span>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {data.topActions.map((action, i) => (
                                <div
                                    key={i}
                                    style={{
                                        display: 'flex',
                                        gap: '0.75rem',
                                        alignItems: 'flex-start',
                                    }}
                                >
                                    <span
                                        style={{
                                            minWidth: '22px',
                                            height: '22px',
                                            borderRadius: '50%',
                                            background: 'rgba(59,123,246,0.15)',
                                            color: 'var(--accent-blue)',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            fontSize: '0.75rem',
                                            fontWeight: 700,
                                            flexShrink: 0,
                                            marginTop: '1px',
                                        }}
                                    >
                                        {i + 1}
                                    </span>
                                    <p
                                        style={{
                                            fontSize: '0.875rem',
                                            color: 'var(--text-primary)',
                                            lineHeight: 1.6,
                                        }}
                                    >
                                        {action}
                                    </p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Risk Breakdown */}
                <div style={{ marginBottom: '2rem' }}>
                    <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>
                        Risk Breakdown
                    </h2>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                        {[...riskScores]
                            .sort((a: RiskScore, b: RiskScore) => b.score - a.score)
                            .map((rs) => {
                                const rsTier = getRiskTier(rs.score)
                                const color = TIER_COLORS[rsTier]
                                const catName =
                                    RISK_CATEGORIES.find((c) => c.id === rs.category)?.name ?? rs.category
                                const isOpen = expandedRisk === rs.category
                                return (
                                    <div key={rs.category} className="card" style={{ overflow: 'hidden' }}>
                                        <button
                                            onClick={() => setExpandedRisk(isOpen ? null : rs.category)}
                                            style={{
                                                width: '100%',
                                                background: 'none',
                                                border: 'none',
                                                cursor: 'pointer',
                                                padding: '1rem 1.25rem',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '1rem',
                                                textAlign: 'left',
                                            }}
                                        >
                                            <div
                                                style={{
                                                    width: '44px',
                                                    height: '44px',
                                                    borderRadius: 'var(--radius-md)',
                                                    background: `${color}18`,
                                                    border: `1px solid ${color}30`,
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    flexShrink: 0,
                                                }}
                                            >
                                                <span
                                                    style={{
                                                        fontSize: '1.125rem',
                                                        fontWeight: 800,
                                                        color,
                                                    }}
                                                >
                                                    {rs.score}
                                                </span>
                                            </div>
                                            <div style={{ flex: 1 }}>
                                                <div
                                                    style={{
                                                        fontWeight: 600,
                                                        fontSize: '0.9375rem',
                                                        marginBottom: '2px',
                                                    }}
                                                >
                                                    {catName}
                                                </div>
                                                <div
                                                    style={{
                                                        width: '100%',
                                                        height: '4px',
                                                        background: 'var(--bg-surface-3)',
                                                        borderRadius: '2px',
                                                        overflow: 'hidden',
                                                    }}
                                                >
                                                    <div
                                                        style={{
                                                            height: '100%',
                                                            width: `${(rs.score / 10) * 100}%`,
                                                            background: color,
                                                            borderRadius: '2px',
                                                            transition: 'width 0.6s ease',
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                            <div
                                                style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '0.75rem',
                                                    flexShrink: 0,
                                                }}
                                            >
                                                <RiskBadge tier={rsTier} />
                                                <svg
                                                    width="16"
                                                    height="16"
                                                    viewBox="0 0 24 24"
                                                    fill="none"
                                                    stroke="var(--text-tertiary)"
                                                    strokeWidth="2"
                                                    strokeLinecap="round"
                                                    strokeLinejoin="round"
                                                    style={{
                                                        transform: isOpen ? 'rotate(180deg)' : 'none',
                                                        transition: 'transform 0.2s',
                                                    }}
                                                >
                                                    <polyline points="6 9 12 15 18 9" />
                                                </svg>
                                            </div>
                                        </button>
                                        {isOpen && (
                                            <div
                                                style={{
                                                    padding: '0 1.25rem 1.25rem',
                                                    display: 'flex',
                                                    flexDirection: 'column',
                                                    gap: '0.75rem',
                                                }}
                                            >
                                                <div className="divider" />
                                                {rs.explanation && (
                                                    <p
                                                        style={{
                                                            fontSize: '0.875rem',
                                                            lineHeight: 1.7,
                                                            color: 'var(--text-primary)',
                                                        }}
                                                    >
                                                        {rs.explanation}
                                                    </p>
                                                )}
                                                {rs.evidence && (
                                                    <div
                                                        style={{
                                                            padding: '0.75rem',
                                                            background: 'var(--bg-surface-3)',
                                                            borderRadius: 'var(--radius-sm)',
                                                            borderLeft: `3px solid ${color}`,
                                                        }}
                                                    >
                                                        <div
                                                            style={{
                                                                fontSize: '0.75rem',
                                                                fontWeight: 600,
                                                                color: 'var(--text-tertiary)',
                                                                marginBottom: '0.25rem',
                                                                textTransform: 'uppercase',
                                                                letterSpacing: '0.06em',
                                                            }}
                                                        >
                                                            Evidence
                                                        </div>
                                                        <p
                                                            style={{
                                                                fontSize: '0.8375rem',
                                                                color: 'var(--text-secondary)',
                                                                lineHeight: 1.6,
                                                            }}
                                                        >
                                                            {rs.evidence}
                                                        </p>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )
                            })}
                    </div>
                </div>

                {/* Value Lever Summary */}
                {hasValueLevers && (
                    <div style={{ marginBottom: '2rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>
                            Value Impact
                        </h2>
                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(3, 1fr)',
                                gap: '0.875rem',
                            }}
                        >
                            {leverSummary.map(({ lever, count }) => {
                                const color = LEVER_COLORS[lever] || 'var(--text-secondary)'
                                return (
                                    <div
                                        key={lever}
                                        className="card"
                                        style={{
                                            padding: '1.25rem',
                                            borderTop: `3px solid ${color}`,
                                            cursor: 'pointer',
                                            background:
                                                activeLever === lever ? `${color}10` : 'var(--bg-surface)',
                                        }}
                                        onClick={() => setActiveLever(activeLever === lever ? 'All' : lever)}
                                    >
                                        <div
                                            style={{
                                                fontSize: '0.8rem',
                                                color: 'var(--text-secondary)',
                                                marginBottom: '0.5rem',
                                            }}
                                        >
                                            {lever}
                                        </div>
                                        <div style={{ fontSize: '1.75rem', fontWeight: 800, color }}>
                                            {count}
                                        </div>
                                        <div
                                            style={{
                                                fontSize: '0.75rem',
                                                color: 'var(--text-tertiary)',
                                                marginTop: '0.25rem',
                                            }}
                                        >
                                            {count === 1 ? 'opportunity' : 'opportunities'}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                )}

                {/* Opportunities */}
                <div style={{ marginBottom: '2rem' }}>
                    <div
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: '1rem',
                            flexWrap: 'wrap',
                            gap: '0.75rem',
                        }}
                    >
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>
                            AI Opportunities ({opportunities.length})
                        </h2>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                            {oppCategories.map((cat) => (
                                <button
                                    key={cat}
                                    onClick={() => setActiveOppCat(cat)}
                                    style={{
                                        padding: '0.3rem 0.75rem',
                                        borderRadius: 'var(--radius-full)',
                                        border: '1px solid',
                                        borderColor:
                                            activeOppCat === cat ? 'var(--accent-blue)' : 'var(--border)',
                                        background:
                                            activeOppCat === cat ? 'rgba(59,123,246,0.1)' : 'transparent',
                                        color:
                                            activeOppCat === cat
                                                ? 'var(--accent-blue)'
                                                : 'var(--text-secondary)',
                                        fontSize: '0.8rem',
                                        fontWeight: 500,
                                        cursor: 'pointer',
                                        transition: 'all var(--transition-fast)',
                                    }}
                                >
                                    {cat}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
                        {filteredOpps.map((opp: Opportunity, i: number) => {
                            const isOpen = expandedOpp === `${i}`
                            return (
                                <div key={i} className="card" style={{ overflow: 'hidden' }}>
                                    <button
                                        onClick={() => setExpandedOpp(isOpen ? null : `${i}`)}
                                        style={{
                                            width: '100%',
                                            background: 'none',
                                            border: 'none',
                                            cursor: 'pointer',
                                            padding: '1.25rem',
                                            textAlign: 'left',
                                        }}
                                    >
                                        <div
                                            style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'flex-start',
                                                gap: '1rem',
                                            }}
                                        >
                                            <div style={{ flex: 1 }}>
                                                <div
                                                    style={{
                                                        fontWeight: 700,
                                                        fontSize: '0.9875rem',
                                                        marginBottom: '0.5rem',
                                                    }}
                                                >
                                                    {opp.title}
                                                </div>
                                                <div
                                                    style={{
                                                        display: 'flex',
                                                        gap: '0.5rem',
                                                        flexWrap: 'wrap',
                                                    }}
                                                >
                                                    <ImpactBadge impact={opp.impact_rating} />
                                                    <TimelineBadge timeline={opp.timeline} />
                                                    <span className="badge badge-neutral">
                                                        {opp.strategic_category}
                                                    </span>
                                                    {opp.value_lever && (
                                                        <span
                                                            style={{
                                                                padding: '0.15rem 0.5rem',
                                                                borderRadius: 'var(--radius-full)',
                                                                fontSize: '0.7rem',
                                                                fontWeight: 500,
                                                                border: '1px solid',
                                                                borderColor:
                                                                    LEVER_COLORS[opp.value_lever] ||
                                                                    'var(--text-secondary)',
                                                                color:
                                                                    LEVER_COLORS[opp.value_lever] ||
                                                                    'var(--text-secondary)',
                                                            }}
                                                        >
                                                            {opp.value_lever}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <svg
                                                width="16"
                                                height="16"
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="var(--text-tertiary)"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                style={{
                                                    transform: isOpen ? 'rotate(180deg)' : 'none',
                                                    transition: 'transform 0.2s',
                                                    flexShrink: 0,
                                                    marginTop: '4px',
                                                }}
                                            >
                                                <polyline points="6 9 12 15 18 9" />
                                            </svg>
                                        </div>
                                    </button>

                                    {isOpen && (
                                        <div style={{ padding: '0 1.25rem 1.5rem' }}>
                                            <div className="divider" style={{ marginBottom: '1.25rem' }} />

                                            <p
                                                style={{
                                                    fontSize: '0.9rem',
                                                    lineHeight: 1.75,
                                                    color: 'var(--text-primary)',
                                                    marginBottom: '1.5rem',
                                                    whiteSpace: 'pre-line',
                                                }}
                                            >
                                                {opp.description}
                                            </p>

                                            {opp.implementation_steps &&
                                                opp.implementation_steps.length > 0 && (
                                                    <div style={{ marginBottom: '1.25rem' }}>
                                                        <div
                                                            style={{
                                                                fontWeight: 600,
                                                                fontSize: '0.875rem',
                                                                color: 'var(--text-secondary)',
                                                                marginBottom: '0.75rem',
                                                                textTransform: 'uppercase',
                                                                letterSpacing: '0.06em',
                                                            }}
                                                        >
                                                            Implementation Steps
                                                        </div>
                                                        <div
                                                            style={{
                                                                display: 'flex',
                                                                flexDirection: 'column',
                                                                gap: '0.5rem',
                                                            }}
                                                        >
                                                            {opp.implementation_steps.map((step, si) => (
                                                                <div
                                                                    key={si}
                                                                    style={{
                                                                        display: 'flex',
                                                                        gap: '0.75rem',
                                                                        alignItems: 'flex-start',
                                                                    }}
                                                                >
                                                                    <span
                                                                        style={{
                                                                            minWidth: '22px',
                                                                            height: '22px',
                                                                            borderRadius: '50%',
                                                                            background:
                                                                                'rgba(59,123,246,0.12)',
                                                                            color: 'var(--accent-blue)',
                                                                            display: 'flex',
                                                                            alignItems: 'center',
                                                                            justifyContent: 'center',
                                                                            fontSize: '0.75rem',
                                                                            fontWeight: 700,
                                                                            flexShrink: 0,
                                                                            marginTop: '2px',
                                                                        }}
                                                                    >
                                                                        {si + 1}
                                                                    </span>
                                                                    <p
                                                                        style={{
                                                                            fontSize: '0.875rem',
                                                                            lineHeight: 1.6,
                                                                        }}
                                                                    >
                                                                        {step}
                                                                    </p>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}

                                            <div
                                                style={{
                                                    display: 'grid',
                                                    gridTemplateColumns: '1fr 1fr',
                                                    gap: '0.875rem',
                                                    marginBottom: '1.25rem',
                                                }}
                                            >
                                                <div
                                                    style={{
                                                        padding: '1rem',
                                                        background: 'var(--bg-surface-3)',
                                                        borderRadius: 'var(--radius-md)',
                                                        borderLeft: '3px solid var(--risk-moderate)',
                                                    }}
                                                >
                                                    <div
                                                        style={{
                                                            fontSize: '0.75rem',
                                                            fontWeight: 600,
                                                            color: 'var(--text-tertiary)',
                                                            marginBottom: '0.375rem',
                                                            textTransform: 'uppercase',
                                                            letterSpacing: '0.06em',
                                                        }}
                                                    >
                                                        Estimated Investment
                                                    </div>
                                                    <div
                                                        style={{
                                                            fontWeight: 700,
                                                            color: 'var(--risk-moderate)',
                                                        }}
                                                    >
                                                        {opp.investment_range}
                                                    </div>
                                                </div>
                                                <div
                                                    style={{
                                                        padding: '1rem',
                                                        background: 'var(--bg-surface-3)',
                                                        borderRadius: 'var(--radius-md)',
                                                        borderLeft: '3px solid var(--risk-low)',
                                                    }}
                                                >
                                                    <div
                                                        style={{
                                                            fontSize: '0.75rem',
                                                            fontWeight: 600,
                                                            color: 'var(--text-tertiary)',
                                                            marginBottom: '0.375rem',
                                                            textTransform: 'uppercase',
                                                            letterSpacing: '0.06em',
                                                        }}
                                                    >
                                                        Potential ROI
                                                    </div>
                                                    <div
                                                        style={{
                                                            fontWeight: 600,
                                                            color: 'var(--risk-low)',
                                                            fontSize: '0.9rem',
                                                        }}
                                                    >
                                                        {opp.roi_estimate}
                                                    </div>
                                                </div>
                                            </div>

                                            {opp.related_services && opp.related_services.length > 0 && (
                                                <div>
                                                    <div
                                                        style={{
                                                            fontWeight: 600,
                                                            fontSize: '0.875rem',
                                                            color: 'var(--text-secondary)',
                                                            marginBottom: '0.75rem',
                                                            textTransform: 'uppercase',
                                                            letterSpacing: '0.06em',
                                                        }}
                                                    >
                                                        Implementation Partners
                                                    </div>
                                                    <div
                                                        style={{
                                                            display: 'flex',
                                                            gap: '0.5rem',
                                                            flexWrap: 'wrap',
                                                        }}
                                                    >
                                                        {opp.related_services.map((svc, si) => (
                                                            <span key={si} className="badge badge-neutral">
                                                                {svc}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                    </div>
                </div>

                {/* Document Upload */}
                {documentError && (
                    <div
                        style={{
                            padding: '0.75rem 1rem',
                            background: 'rgba(239,68,68,0.1)',
                            borderRadius: 'var(--radius-sm)',
                            color: 'var(--risk-critical)',
                            fontSize: '0.875rem',
                            marginBottom: '1rem',
                        }}
                    >
                        {documentError}
                    </div>
                )}
                <DocumentUpload
                    analysisId={analysisId}
                    documents={documents}
                    onDocumentsChange={handleDocumentsChange}
                    onReanalyze={handleReanalyze}
                    reanalyzing={reanalyzing}
                />

                {/* EBITDA Impact Model */}
                {data.ebitdaTree && (
                    <div style={{ marginBottom: '2rem' }}>
                        <h2 style={{ fontSize: '1.125rem', fontWeight: 700, marginBottom: '1rem' }}>
                            EBITDA Impact Model
                        </h2>

                        <div
                            style={{
                                display: 'flex',
                                gap: '0.5rem',
                                flexWrap: 'wrap',
                                marginBottom: '1rem',
                            }}
                        >
                            {data.ebitdaTree.revenueEstimate && (
                                <span className="badge badge-low">
                                    Revenue: {data.ebitdaTree.revenueEstimate}
                                </span>
                            )}
                            {data.ebitdaTree.ebitdaEstimate && (
                                <span className="badge badge-blue">
                                    EBITDA: {data.ebitdaTree.ebitdaEstimate}
                                </span>
                            )}
                        </div>

                        {data.ebitdaTree.businessModelSummary && (
                            <p
                                style={{
                                    fontSize: '0.9rem',
                                    lineHeight: 1.7,
                                    color: 'var(--text-secondary)',
                                    marginBottom: '1.25rem',
                                }}
                            >
                                {data.ebitdaTree.businessModelSummary}
                            </p>
                        )}

                        <div className="card" style={{ padding: '1rem' }}>
                            <EbitdaTree treeData={data.ebitdaTree.treeData} opportunities={opportunities} />
                        </div>
                    </div>
                )}
            </main>
        </div>
    )
}
