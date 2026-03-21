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
import RiskBreakdown, { CAT_LABELS } from '@/components/RiskBreakdown'
import ValueLeverSummary from '@/components/ValueLeverSummary'
import OpportunitiesList from '@/components/OpportunitiesList'
import { getRiskTier, RISK_CATEGORIES, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { AnalysisData, DocumentInfo } from '@/lib/types/api'

const EbitdaTree = dynamic(() => import('@/components/EbitdaTree'), { ssr: false })

export default function AnalysisDetail({ data, analysisId }: { data: AnalysisData; analysisId: string }) {
    const router = useRouter()
    const [activeLever, setActiveLever] = useState<string>('All')
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

                <RiskBreakdown riskScores={riskScores} />

                <ValueLeverSummary
                    opportunities={opportunities}
                    activeLever={activeLever}
                    onLeverChange={setActiveLever}
                />

                <OpportunitiesList opportunities={opportunities} activeLever={activeLever} />

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
