export interface RiskScore {
    category: string
    score: number
    rationale?: string
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
    implementation_steps?: string[]
    investment_range?: string
    roi_estimate?: string
    related_services?: string[]
    value_lever?: 'Revenue Side' | 'Cost Side' | 'Both'
}

export interface EbitdaNode {
    id: string
    label: string
    type: 'revenue' | 'cost' | 'margin' | 'subtotal'
    value_range?: string
    percentage_of_parent?: number
    description: string
    linked_opportunity_indices: number[]
    parent_id?: string | null
    children?: EbitdaNode[]
}

export interface EbitdaTree {
    treeData: EbitdaNode[]
    revenueEstimate?: string
    ebitdaEstimate?: string
    businessModelSummary?: string
}

export interface ValueChainStep {
    id: string
    label: string
    description: string
    category: 'primary' | 'support'
    risk_categories: string[]
    opportunity_indices: number[]
}

export interface ValueChain {
    steps: ValueChainStep[]
    summary: string
}

export interface DocumentInfo {
    id: string
    filename: string
    fileType: string
    charCount: number
    uploadedAt: string
}

export interface AnalysisData {
    id: string
    companyName: string
    companyUrl?: string
    industry?: string
    overallRiskScore: number | null
    riskTier: 'low' | 'moderate' | 'high' | 'critical' | null
    analysisSummary?: string
    riskScores: RiskScore[]
    opportunities: Opportunity[]
    topActions?: string[]
    ebitdaTree?: EbitdaTree
    valueChain?: ValueChain
    documents?: DocumentInfo[]
    analyzedAt?: string
    error?: string | null
    scanType?: string
    pipelineProgress?: number
    pipelineLabel?: string
    scanId?: string
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

export interface ScanAnalysis {
    id: string
    companyName: string
    companyUrl: string
    industry: string
    overallRiskScore: number | null
    riskTier: string | null
    error: string | null
    analyzedAt: string | null
}

export interface ScanData {
    status: string
    progress: number
    type: string
    portfolioCompanies: Array<{ name: string; url: string }>
    analyses: ScanAnalysis[]
}

export interface DashboardData {
    totalAnalyses: number
    avgRiskScore: number
    criticalCount: number
    scanCount: number
    recentAnalyses: AnalysisItem[]
    recentScans: ScanItem[]
}
