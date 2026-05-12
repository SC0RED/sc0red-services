import { formatAbsoluteUTC, parseIsoDate } from '@/lib/utils/dateFormat'
import { getRiskTier } from '@/lib/utils/riskUtils'
import { capitalise } from '@/lib/utils/stringUtils'
import type { AnalysisData } from '@/lib/types/api'

/**
 * One-line executive summary strap rendered between the page header and
 * the overview cards. Built for the PE buy-side reader who triages an
 * analysis in 30-90 seconds and may not scroll past the fold — the strap
 * compresses the analysis into a transcribable headline they can copy
 * straight into an investment memo.
 *
 * Format:
 *   {company} — AI Risk {score} / {tier} · {N} opportunities · est. EBITDA range {range} · last analysed {date}
 *
 * The EBITDA and last-analysed segments (with their leading separators)
 * are dropped entirely when their source data is absent — partial-data
 * placeholders ("—", "N/A") would cheapen what is meant to be an
 * analyst-grade summary. See design D2 + D4 for rationale.
 *
 * Style: inline text, `·` separators, NO `white-space: nowrap`. On
 * narrow viewports the strap wraps naturally to 2-3 lines per resolved
 * question 2 in the change's design.md.
 */
export default function AnalysisExecutiveStrap({ data }: { data: AnalysisData }) {
    // Use `typeof score === 'number'` rather than `score !== null` —
    // the API contract types `overallRiskScore` as `number | null`,
    // but the wider type guard defends against contract drift (e.g.
    // a future schema relaxation that introduces `undefined`) and
    // gracefully drops the entire section if `NaN` ever sneaks in,
    // since `Number.isFinite(NaN)` is false. Cheap defence-in-depth
    // for a marketing-grade summary strap.
    const score = data.overallRiskScore
    const hasScore = typeof score === 'number' && Number.isFinite(score)
    const tier = data.riskTier ?? (hasScore ? getRiskTier(score) : null)
    const tierLabel = tier ? capitalise(tier) : '—'
    const scoreLabel = hasScore ? score.toFixed(1) : '—'

    // Build segments after the headline. Each segment is conditionally
    // included so missing data drops cleanly without orphan separators.
    const segments: string[] = [`${data.opportunities?.length ?? 0} opportunities`]
    if (data.ebitdaTree?.ebitdaEstimate) {
        segments.push(`est. EBITDA range ${data.ebitdaTree.ebitdaEstimate}`)
    }
    const analysedAtDate = parseIsoDate(data.analyzedAt)
    if (analysedAtDate) {
        // UTC-deterministic format ("May 5, 2026") — matches the
        // SSR-safe pattern used by `RelativeTime`. Hand-composed UTC
        // beats `toLocaleDateString` because it produces identical
        // strings across any server/client timezone pair.
        segments.push(`last analysed ${formatAbsoluteUTC(analysedAtDate)}`)
    }

    return (
        <div
            data-testid="analysis-executive-strap"
            style={{
                marginBottom: '1.25rem',
                padding: '0.75rem 1rem',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.875rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.5,
            }}
        >
            <strong style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{data.companyName}</strong>
            <span aria-hidden="true"> — </span>
            <span>
                AI Risk{' '}
                <strong style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{scoreLabel}</strong> /{' '}
                <strong style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{tierLabel}</strong>
            </span>
            {segments.map((segment) => (
                <span key={segment}>
                    <span aria-hidden="true"> · </span>
                    {segment}
                </span>
            ))}
        </div>
    )
}
