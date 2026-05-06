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

export const RISK_CATEGORY_COLORS: Record<string, string> = {
    competitive_displacement: '#ef4444',
    technology_obsolescence: '#f59e0b',
    talent_workforce: '#8b5cf6',
    margin_compression: '#ec4899',
    customer_behavior: '#06b6d4',
    regulatory_compliance: '#10b981',
    supply_chain: '#f97316',
    data_ip: '#6366f1',
}

/**
 * Short labels used in chart axes and value-chain chips, where the
 * full `RISK_CATEGORIES[*].name` doesn't fit. Lives here (not in
 * `RiskBreakdown.tsx`) so server-rendered code paths — including the
 * print PDF route — can import it without dragging the
 * `'use client'`-flagged screen component into the server bundle.
 */
export const CAT_LABELS: Record<string, string> = {
    competitive_displacement: 'Competitive Displ.',
    technology_obsolescence: 'Tech Obsolescence',
    talent_workforce: 'Talent & Workforce',
    margin_compression: 'Margin Compression',
    customer_behavior: 'Customer Behavior',
    regulatory_compliance: 'Regulatory',
    supply_chain: 'Supply Chain',
    data_ip: 'Data & IP',
}

export const TIER_COLORS: Record<string, string> = {
    low: 'var(--risk-low)',
    moderate: 'var(--risk-moderate)',
    high: 'var(--risk-high)',
    critical: 'var(--risk-critical)',
}

export const TIER_BG_COLORS: Record<string, string> = {
    low: 'var(--risk-low-bg)',
    moderate: 'var(--risk-moderate-bg)',
    high: 'var(--risk-high-bg)',
    critical: 'var(--risk-critical-bg)',
}

export const TIER_COLORS_HEX: Record<string, string> = {
    low: '#22C55E',
    moderate: '#F59E0B',
    high: '#F97316',
    critical: '#EF4444',
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
