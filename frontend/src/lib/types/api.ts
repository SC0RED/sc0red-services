export interface RiskScore {
    category: string
    score: number
    explanation?: string
    evidence?: string
}

export interface Vendor {
    name: string
    url: string
    specialty: string
}

export interface RelatedService {
    service_type: string
    vendors: Vendor[]
}

export interface Opportunity {
    title: string
    description: string
    impact_rating: 'High' | 'Medium' | 'Low'
    timeline: string
    strategic_category: string
    risk_mitigated?: string
    implementation_steps?: string[]
    investment_range?: string
    roi_estimate?: string
    related_services?: RelatedService[]
}

export interface AnalysisData {
    id: string
    companyName: string
    companyUrl?: string
    industry?: string
    overallRiskScore: number
    riskTier: 'low' | 'moderate' | 'high' | 'critical'
    analysisSummary?: string
    riskScores: RiskScore[]
    opportunities: Opportunity[]
    topActions?: string[]
    analyzedAt?: string
    scanType?: string
}

export interface AnalysisItem {
    id: string
    companyName: string
    companyUrl?: string
    industry?: string
    overallRiskScore: number | null
    riskTier: string | null
    analyzedAt: string | null
    scanType?: string
}

export interface ScanItem {
    id: string
    sourceUrl: string
    type: string
    status: string
    progress: number
    completedCount: number
    createdAt: string
}

export interface DashboardData {
    totalAnalyses: number
    avgRiskScore: number
    criticalCount: number
    scanCount: number
    recentAnalyses: AnalysisItem[]
    recentScans: ScanItem[]
}
