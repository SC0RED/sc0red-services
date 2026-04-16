'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import dynamic from 'next/dynamic'
import { useRouter } from 'next/navigation'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer } from 'recharts'

import DocumentUpload from '@/components/DocumentUpload'
import RiskBadge from '@/components/RiskBadge'
import RiskBreakdown, { CAT_LABELS } from '@/components/RiskBreakdown'
import ValueLeverSummary from '@/components/ValueLeverSummary'
import OpportunitiesList from '@/components/OpportunitiesList'
import AnalysisHeader from '@/components/analysis/AnalysisHeader'
import EbitdaSection from '@/components/analysis/EbitdaSection'
import FailedAnalysisView from '@/components/analysis/FailedAnalysisView'
import TopActionsCallout from '@/components/analysis/TopActionsCallout'
import { LoadingSpinner } from '@/components/ui'
import { useScanRealtime } from '@/lib/hooks/useScanRealtime'
import { exportAnalysisDetailCsv } from '@/lib/utils/csvExport'
import { getRiskTier, RISK_CATEGORIES, TIER_COLORS } from '@/lib/utils/riskUtils'
import type { AnalysisData, DocumentInfo } from '@/lib/types/api'

const ValueChainDiagram = dynamic(() => import('@/components/ValueChainDiagram'), {
    loading: () => (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem' }}>
            <LoadingSpinner />
        </div>
    ),
    ssr: false,
})

export default function AnalysisDetail({ data, analysisId }: { data: AnalysisData; analysisId: string }) {
    const router = useRouter()
    const [activeLever, setActiveLever] = useState<string>('All')
    const [documents, setDocuments] = useState<DocumentInfo[]>(data.documents ?? [])
    const [reanalyzing, setReanalyzing] = useState(false)
    const [reanalysisProgress, setReanalysisProgress] = useState(0)
    const [reanalysisLabel, setReanalysisLabel] = useState('')
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

    const reanalysisRealtime = useScanRealtime({
        onProgress: (progress, label) => {
            setReanalysisProgress((prev) => Math.max(prev, progress))
            if (label) setReanalysisLabel(label)
        },
        onComplete: () => {
            setReanalysisProgress(100)
            setReanalysisLabel('Re-analysis complete!')
            setReanalyzing(false)
            abortControllerRef.current?.abort()
            reanalysisRealtime.stop()
            router.refresh()
        },
        onFailed: (error) => {
            setDocumentError(error)
            setReanalyzing(false)
            reanalysisRealtime.stop()
        },
    })

    const handleReanalyze = useCallback(async () => {
        setReanalyzing(true)
        setReanalysisProgress(0)
        setReanalysisLabel('')
        setDocumentError(null)
        const controller = new AbortController()
        abortControllerRef.current = controller
        try {
            const response = await fetch(`/api/analysis/${analysisId}/reanalyze`, {
                method: 'POST',
                signal: controller.signal,
            })
            if (!response.ok) throw new Error('Re-analysis failed')

            const responseData = (await response.json()) as { status: string; scanId?: string }
            const reanalyzeScanId = responseData.scanId

            let realtimeConnected = false
            if (reanalyzeScanId) {
                realtimeConnected = await reanalysisRealtime.start(reanalyzeScanId)
            }

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

                    // Update progress from poll data when realtime is not connected
                    if (!realtimeConnected) {
                        const pollProgress = updated.pipelineProgress ?? 0
                        const pollLabel = updated.pipelineLabel ?? ''
                        if (pollProgress > 0) {
                            setReanalysisProgress((prev) => Math.max(prev, pollProgress))
                        }
                        if (pollLabel) {
                            setReanalysisLabel(pollLabel)
                        }
                    }

                    if (updated.analyzedAt && updated.analyzedAt !== originalAnalyzedAt) {
                        reanalysisRealtime.stop()
                        router.refresh()
                        return
                    }
                } catch (error: unknown) {
                    if (error instanceof DOMException && error.name === 'AbortError') return
                    throw error
                }
            }

            reanalysisRealtime.stop()
            router.refresh()
        } catch (error: unknown) {
            if (error instanceof DOMException && error.name === 'AbortError') return
            const message = error instanceof Error ? error.message : 'Re-analysis failed'
            setDocumentError(message)
        } finally {
            setReanalyzing(false)
            setReanalysisProgress(0)
            setReanalysisLabel('')
            abortControllerRef.current = null
        }
    }, [analysisId, data.analyzedAt, router, reanalysisRealtime])

    const riskScores = data.riskScores ?? []
    const opportunities = data.opportunities ?? []

    const tier = data.riskTier || getRiskTier(data.overallRiskScore ?? 0)
    const tierColor = TIER_COLORS[tier] || 'var(--text-secondary)'

    const radarData = RISK_CATEGORIES.map((cat) => {
        const rs = riskScores.find((r) => r.category === cat.id)
        return { category: CAT_LABELS[cat.id] ?? cat.name, score: rs?.score ?? 0, fullMark: 10 }
    })

    // Failed analysis — show error + retry UI instead of the full analysis.
    if (data.error && !data.analyzedAt) {
        return (
            <FailedAnalysisView
                analysisId={analysisId}
                companyName={data.companyName}
                companyUrl={data.companyUrl}
                error={data.error}
                scanId={data.scanId}
                documents={documents}
                documentError={documentError}
                reanalyzing={reanalyzing}
                reanalysisProgress={reanalysisProgress}
                reanalysisLabel={reanalysisLabel}
                onRetry={handleReanalyze}
                onDocumentsChange={handleDocumentsChange}
            />
        )
    }

    return (
        <>
            <AnalysisHeader
                analysisId={analysisId}
                companyName={data.companyName}
                companyUrl={data.companyUrl}
                industry={data.industry}
                tier={tier}
                onExportCsv={() => exportAnalysisDetailCsv(data)}
            />

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

            <TopActionsCallout actions={data.topActions ?? []} />

            <RiskBreakdown riskScores={riskScores} />

            <ValueLeverSummary
                opportunities={opportunities}
                activeLever={activeLever}
                onLeverChange={setActiveLever}
            />

            <OpportunitiesList opportunities={opportunities} activeLever={activeLever} />

            {data.valueChain && data.valueChain.steps.length > 0 && (
                <ValueChainDiagram
                    steps={data.valueChain.steps}
                    opportunities={opportunities}
                    summary={data.valueChain.summary}
                />
            )}

            {/* Re-analysis Progress */}
            {reanalyzing && (
                <div
                    className="card"
                    style={{ padding: '1.5rem', marginBottom: '1.5rem', textAlign: 'center' }}
                >
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                        Re-analyzing with documents...
                    </h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
                        {reanalysisLabel || 'Starting pipeline...'}
                    </p>
                    <div className="progress-bar" style={{ maxWidth: '360px', margin: '0 auto' }}>
                        <div className="progress-fill" style={{ width: `${reanalysisProgress}%` }} />
                    </div>
                    <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                        {reanalysisProgress}% complete
                    </div>
                </div>
            )}

            {/* Document Upload */}
            {documentError && (
                <div className="alert-error" style={{ marginBottom: '1rem' }}>
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

            {data.ebitdaTree && <EbitdaSection ebitdaTree={data.ebitdaTree} opportunities={opportunities} />}
        </>
    )
}
