import { TIER_COLORS } from '@/lib/utils/riskUtils'
import type { AnalysisData } from '@/lib/types/api'

interface PrintCoverProps {
    analysis: AnalysisData
    /** Already-formatted "Generated <date>" string from the parent. */
    generatedDate: string
}

/**
 * Cover page of the printed PDF — company name, source URL, industry,
 * overall score with tier badge, two-sentence thesis (analysisSummary),
 * and the generation date.
 *
 * Extracted from the previous `PrintReport.tsx` cover block with no
 * behaviour change. Lives here so the rewritten `PrintReport`
 * composition stays scannable and so future cover-only changes don't
 * have to touch the orchestrator.
 */
export default function PrintCover({ analysis, generatedDate }: PrintCoverProps) {
    const tier = analysis.riskTier ?? 'moderate'
    const tierColor = TIER_COLORS[tier] ?? 'var(--text-secondary)'

    return (
        <section className="print-cover">
            <div className="print-cover-eyebrow">sc0red Advisory · AI Risk Report</div>
            <h1 className="print-cover-title">{analysis.companyName}</h1>
            {analysis.companyUrl ? <p className="print-cover-meta">{analysis.companyUrl}</p> : null}
            {analysis.industry ? <p className="print-cover-meta">{analysis.industry}</p> : null}
            <div className="print-cover-score" style={{ borderColor: tierColor, color: tierColor }}>
                {analysis.overallRiskScore != null ? analysis.overallRiskScore.toFixed(1) : '—'}
            </div>
            <div>
                <span
                    className="badge"
                    style={{
                        background: 'var(--accent-blue-glow)',
                        color: tierColor,
                        border: `1px solid ${tierColor}`,
                        padding: '4px 12px',
                        borderRadius: '999px',
                        fontWeight: 600,
                        fontSize: '0.8125rem',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                    }}
                >
                    {tier} risk
                </span>
            </div>
            {analysis.analysisSummary ? (
                <p
                    style={{
                        marginTop: '24px',
                        maxWidth: '640px',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.65,
                    }}
                >
                    {analysis.analysisSummary}
                </p>
            ) : null}
            <p
                style={{
                    marginTop: '32px',
                    color: 'var(--text-tertiary)',
                    fontSize: '0.875rem',
                }}
            >
                Generated {generatedDate} · sc0red Advisory
            </p>
        </section>
    )
}
