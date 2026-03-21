export const RISK_CATEGORIES = [
    {
        id: 'competitive_displacement',
        name: 'Competitive Displacement',
        description: 'Risk of AI-native competitors capturing market share',
        icon: 'Swords',
    },
    {
        id: 'technology_obsolescence',
        name: 'Technology Obsolescence',
        description: 'Risk that core products/services become obsolete due to AI',
        icon: 'Cpu',
    },
    {
        id: 'talent_workforce',
        name: 'Talent & Workforce',
        description: 'Risk that AI automates key workforce functions',
        icon: 'Users',
    },
    {
        id: 'margin_compression',
        name: 'Margin Compression',
        description: 'Risk that AI enables competitors to operate at dramatically lower costs',
        icon: 'TrendingDown',
    },
    {
        id: 'customer_behavior',
        name: 'Customer Behavior Shift',
        description: 'Risk that customers adopt AI-powered alternatives',
        icon: 'ShoppingCart',
    },
    {
        id: 'regulatory_compliance',
        name: 'Regulatory & Compliance',
        description: 'Risk from emerging AI regulations',
        icon: 'Scale',
    },
    {
        id: 'supply_chain',
        name: 'Supply Chain & Vendor',
        description: 'Risk that key suppliers are disrupted by AI',
        icon: 'Package',
    },
    {
        id: 'data_ip',
        name: 'Data & IP Vulnerability',
        description: 'Risk that proprietary data or IP loses value',
        icon: 'Lock',
    },
] as const

export type RiskCategoryId = (typeof RISK_CATEGORIES)[number]['id']

export const STRATEGIC_CATEGORIES = [
    'Competitive Moat',
    'Revenue Capture',
    'Market Expansion',
    'Operational Efficiency',
    'Talent Strategy',
] as const

export type StrategicCategory = (typeof STRATEGIC_CATEGORIES)[number]

export const TIER_COLORS: Record<string, string> = {
    low: 'var(--risk-low)',
    moderate: 'var(--risk-moderate)',
    high: 'var(--risk-high)',
    critical: 'var(--risk-critical)',
}

export function getRiskTier(score: number): 'low' | 'moderate' | 'high' | 'critical' {
    if (score <= 3) return 'low'
    if (score <= 6) return 'moderate'
    if (score <= 8) return 'high'
    return 'critical'
}

export function getRiskTierLabel(tier: string): string {
    const labels: Record<string, string> = {
        low: 'Low Risk',
        moderate: 'Moderate Risk',
        high: 'High Risk',
        critical: 'Critical Risk',
    }
    return labels[tier] || tier
}

export function getRiskColor(tier: string): string {
    const colors: Record<string, string> = {
        low: 'var(--risk-low)',
        moderate: 'var(--risk-moderate)',
        high: 'var(--risk-high)',
        critical: 'var(--risk-critical)',
    }
    return colors[tier] || 'var(--text-secondary)'
}

export function getImpactColor(impact: string): string {
    const colors: Record<string, string> = {
        High: 'var(--risk-low)',
        Medium: 'var(--risk-moderate)',
        Low: 'var(--text-secondary)',
    }
    return colors[impact] || 'var(--text-secondary)'
}

export function formatInvestment(range: string): string {
    return range || 'To be estimated'
}

export function calculateOverallScore(scores: Array<{ score: number }>): number {
    if (!scores.length) return 0
    const total = scores.reduce((sum, s) => sum + s.score, 0)
    return Math.round((total / scores.length) * 10) / 10
}
