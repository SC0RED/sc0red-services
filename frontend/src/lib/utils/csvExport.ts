import type { AnalysisData, AnalysisItem, RiskScore } from '@/lib/types/api'
import { RISK_CATEGORIES } from '@/lib/utils/riskUtils'

function escapeCell(value: string | number | null | undefined): string {
    if (value === null || value === undefined) return ''
    const str = String(value)
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`
    }
    return str
}

function buildRow(cells: (string | number | null | undefined)[]): string {
    return cells.map(escapeCell).join(',')
}

function triggerDownload(csvContent: string, filename: string): void {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
}

export function exportAnalysisDetailCsv(data: AnalysisData): void {
    const lines: string[] = []

    // Company info
    lines.push(buildRow(['Company', data.companyName]))
    lines.push(buildRow(['URL', data.companyUrl ?? '']))
    lines.push(buildRow(['Industry', data.industry ?? '']))
    lines.push(buildRow(['Overall Risk Score', data.overallRiskScore]))
    lines.push(buildRow(['Risk Tier', data.riskTier]))
    lines.push(buildRow(['Analyzed At', data.analyzedAt ?? '']))
    lines.push('')

    // Risk scores
    lines.push(buildRow(['Risk Category', 'Score', 'Rationale']))
    const riskScores = data.riskScores ?? []
    for (const cat of RISK_CATEGORIES) {
        const score = riskScores.find((r: RiskScore) => r.category === cat.id)
        lines.push(buildRow([cat.name, score?.score ?? 0, score?.rationale ?? '']))
    }
    lines.push('')

    // Opportunities
    lines.push(
        buildRow([
            'Opportunity',
            'Impact',
            'Timeline',
            'Category',
            'Value Lever',
            'Investment Range',
            'ROI Estimate',
        ])
    )
    for (const opp of data.opportunities ?? []) {
        lines.push(
            buildRow([
                opp.title,
                opp.impact_rating,
                opp.timeline,
                opp.strategic_category,
                opp.value_lever ?? '',
                opp.investment_range ?? '',
                opp.roi_estimate ?? '',
            ])
        )
    }

    const filename = `${data.companyName.replace(/[^a-zA-Z0-9]/g, '_')}_analysis.csv`
    triggerDownload(lines.join('\n'), filename)
}

export function exportAnalysesListCsv(analyses: AnalysisItem[]): void {
    const lines: string[] = []

    lines.push(buildRow(['Company', 'Industry', 'Risk Score', 'Risk Tier', 'Source', 'Analyzed At']))
    for (const a of analyses) {
        lines.push(
            buildRow([
                a.companyName,
                a.industry ?? '',
                a.overallRiskScore,
                a.riskTier ?? '',
                a.scanType ?? '',
                a.analyzedAt ?? '',
            ])
        )
    }

    triggerDownload(lines.join('\n'), 'analyses_export.csv')
}
