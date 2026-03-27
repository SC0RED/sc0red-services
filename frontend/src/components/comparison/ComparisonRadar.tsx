'use client'

import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Legend } from 'recharts'

import { COMPARISON_COLORS } from '@/components/comparison/ComparisonScoreCards'
import { RISK_CATEGORIES } from '@/lib/utils/riskUtils'
import { CAT_LABELS } from '@/components/RiskBreakdown'
import type { AnalysisData } from '@/lib/types/api'

interface ComparisonRadarProps {
    analyses: AnalysisData[]
}

export default function ComparisonRadar({ analyses }: ComparisonRadarProps) {
    const radarData = RISK_CATEGORIES.map((cat) => {
        const point: Record<string, string | number> = {
            category: CAT_LABELS[cat.id] ?? cat.name,
        }
        analyses.forEach((analysis, index) => {
            const riskScore = analysis.riskScores?.find((r) => r.category === cat.id)
            point[`company${index}`] = riskScore?.score ?? 0
        })
        return point
    })

    return (
        <div className="card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
            <div style={{ fontWeight: 600, marginBottom: '1rem', fontSize: '0.9375rem' }}>
                Risk Profile Comparison
            </div>
            <ResponsiveContainer width="100%" height={340}>
                <RadarChart data={radarData}>
                    <PolarGrid stroke="var(--border)" />
                    <PolarAngleAxis
                        dataKey="category"
                        tick={{ fill: 'var(--text-primary)', fontSize: 11, fontWeight: 500 }}
                    />
                    {analyses.map((analysis, index) => (
                        <Radar
                            key={analysis.id}
                            name={analysis.companyName}
                            dataKey={`company${index}`}
                            stroke={COMPARISON_COLORS[index]}
                            fill={COMPARISON_COLORS[index]}
                            fillOpacity={0.08}
                            strokeWidth={2}
                        />
                    ))}
                    <Legend wrapperStyle={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }} />
                </RadarChart>
            </ResponsiveContainer>
        </div>
    )
}
