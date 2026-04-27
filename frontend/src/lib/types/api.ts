export interface RiskScore {
    category: string
    score: number
    rationale?: string
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
    error?: string
    scanType?: string
    pipelineProgress?: number
    pipelineLabel?: string
    scanId?: string
    /** The PE-firm URL (or company URL for standalone) the parent scan was started from. */
    scanSourceUrl?: string
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
    scanId?: string
}

export interface ScanItem {
    id: string
    sourceUrl: string
    type: string
    status: string
    progress: number
    completedCount: number
    /**
     * Total linked companies at confirm time. Used to size the cascade
     * scope in the delete-scan toast (deletion touches every linked
     * company, not just completed ones — `completedCount` would
     * underreport for in-flight scans).
     */
    totalCompanies?: number
    createdAt: string
}

/**
 * Lifecycle state of a single company card on the portfolio view.
 *
 * Backend collapses two backend-internal states (no record yet vs.
 * record-but-progress=0) into one UI state called `pending`. Failure
 * takes precedence over completion: a record with both `error` set and
 * a stale `analyzedAt` is reported as `failed`.
 */
export type ScanAnalysisState = 'pending' | 'scanning' | 'done' | 'failed'

export interface ScanAnalysis {
    id: string
    companyName: string
    companyUrl: string
    industry: string
    overallRiskScore: number | null
    riskTier: string | null
    error: string | null
    analyzedAt: string | null
    pipelineProgress?: number
    pipelineLabel?: string
    /** Explicit lifecycle state — frontend renders directly off this. */
    state: ScanAnalysisState
    /**
     * Zero-based submission position from the scan_company link record.
     * `null` for legacy link records written before this field was added;
     * such entries sort after entries with a numeric orderIndex.
     */
    orderIndex: number | null
}

export interface ScanData {
    status: string
    progress: number
    type: string
    totalCompanies?: number
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

/**
 * Org-level event surfaced in the activity panel.
 *
 * Server-projected from existing DynamoDB records — see
 * `backend/src/handlers/activity_handlers.py` for the source-of-truth
 * mapping. Each event is identified by a deterministic `id`
 * (`{type}:{source-record-id}`) so the frontend can dedupe across poll
 * cycles without server help.
 */
export type ActivityEventType = 'scan_started' | 'analysis_completed' | 'member_invited' | 'member_joined'

export interface ActivityActor {
    id: string
    name: string
}

export interface ActivityTarget {
    id: string
    name: string
    /** Logical category — `scan` | `analysis` | `invitation` | `user`. */
    type: string
}

export interface ActivityEvent {
    id: string
    type: ActivityEventType
    actor: ActivityActor
    target: ActivityTarget
    /** ISO 8601 timestamp; consumed by `<RelativeTime>`. */
    timestamp: string
    summary: string
}

export interface ActivityEventsResponse {
    events: ActivityEvent[]
}
