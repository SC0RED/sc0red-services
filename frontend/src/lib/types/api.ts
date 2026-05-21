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
    // Numeric ROI × Investment axes for the Quick Wins matrix scatter
    // plot (Phase 14 of redesign-analysis-visuals, design D8).
    // ``null`` / undefined → opportunity routes to the matrix's
    // "uncalibrated" footer strip rather than the main scatter.
    // Range constraints (enforced server-side):
    //   - ``investment_value_usd``: integer >= 0 (USD).
    //   - ``roi_estimate_pct``: number 0..500 (renderer clamps at 300%).
    investment_value_usd?: number | null
    roi_estimate_pct?: number | null
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
    /** Per-node derivation provenance — see `ebitda-tree-confidence`
     *  capability spec. `null` / undefined for rollup (subtotal/margin) nodes
     *  and for any record stored before the confidence fields were added; the
     *  frontend suppresses the chip in those cases (no "unknown" badge). */
    confidence_level?: 'high' | 'medium' | 'low' | null
    confidence_basis?: string | null
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
    /** AI-generated Balanced Scorecard strategy map (sc0red Advisory).
     * Optional because legacy analyses pre-date this field. */
    strategyMap?: StrategyMap
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

// ── Strategy Map ─────────────────────────────────────────────────────────
//
// Mirrors the JSON schema at
// `backend/src/pipeline/prompts/strategy_map/schemas/strategy_map_output.json`
// and the pydantic model at `backend/src/models/model_strategy_map.py`.
// Backend serialises with `by_alias=True` so the wire shape is camelCase.

/** Per-objective AI confidence in the inference. */
export type ConfidenceMarker = 'HIGH' | 'MEDIUM' | 'LOW'

export type ValueProposition =
    | 'operational_excellence'
    | 'customer_intimacy'
    | 'product_leadership'
    | 'hybrid'

export interface ValuePropositionClassification {
    primary: ValueProposition
    /** Only populated when `primary === 'hybrid'`. */
    secondary?: 'operational_excellence' | 'customer_intimacy' | 'product_leadership' | null
    rationale: string
    /** Brand exemplar (e.g. "Mobil"). Nullable on the wire — see
     *  `rationale_source` doc for the OpenAI strict-mode rationale. */
    exemplar_company?: string | null
}

export interface VisionStatement {
    statement: string
    synthesised: boolean
    rationale: string
}

export interface MissionStatement {
    statement: string
    synthesised: boolean
    rationale: string
}

export interface StrategicPriority {
    name: string
    result: string
}

export interface FinancialObjective {
    id: string
    title: string
    definition: string
    category: 'revenue_growth' | 'productivity'
    confidence: ConfidenceMarker
    /** Optional traceability note. Backend serialises `null` (not missing)
     *  when the AI didn't supply one — OpenAI strict mode requires the
     *  field to be present, so use `?? ''` when rendering. */
    rationale_source?: string | null
    /** Index pointers into the analysis's `opportunities` array — same
     *  idiom as `ValueChainStep.opportunity_indices` and
     *  `EbitdaNode.linked_opportunity_indices`. Renders as coloured
     *  opportunity dots on the BSC strategy-map cell.
     *
     *  Phase 1a of the `redesign-analysis-visuals` change ships only the
     *  data shape: persisted records produced before this change carry
     *  no value (deserialise to `undefined`); the AI does not yet
     *  populate it (Phase 1b). Renderers MUST treat `undefined`,
     *  missing, and empty-array as semantically identical "no links". */
    linked_opportunity_indices?: number[]
}

export interface CustomerObjective {
    id: string
    /** First-person customer-voice quote (Vector house style).
     * Renderer adds the surrounding quote marks. */
    title: string
    definition: string
    panel: 'consumer' | 'channel' | 'partner'
    confidence: ConfidenceMarker
    /** Optional traceability note. Backend serialises `null` (not missing)
     *  when the AI didn't supply one — OpenAI strict mode requires the
     *  field to be present, so use `?? ''` when rendering. */
    rationale_source?: string | null
    /** See `FinancialObjective.linked_opportunity_indices`. */
    linked_opportunity_indices?: number[]
}

export interface InternalProcessObjective {
    id: string
    title: string
    definition: string
    category: 'innovation' | 'customer_management' | 'operational_excellence' | 'citizenship'
    confidence: ConfidenceMarker
    /** Optional traceability note. Backend serialises `null` (not missing)
     *  when the AI didn't supply one — OpenAI strict mode requires the
     *  field to be present, so use `?? ''` when rendering. */
    rationale_source?: string | null
    /** See `FinancialObjective.linked_opportunity_indices`. */
    linked_opportunity_indices?: number[]
}

export interface InternalProcessTheme {
    name: string
    supports_financial_objectives: string[]
    objectives: InternalProcessObjective[]
}

export interface CapacityObjective {
    id: string
    title: string
    definition: string
    confidence: ConfidenceMarker
    /** Optional traceability note. Backend serialises `null` (not missing)
     *  when the AI didn't supply one — OpenAI strict mode requires the
     *  field to be present, so use `?? ''` when rendering. */
    rationale_source?: string | null
    /** See `FinancialObjective.linked_opportunity_indices`. */
    linked_opportunity_indices?: number[]
}

export interface OrganizationalCapacityPerspective {
    people: CapacityObjective
    technology: CapacityObjective
    culture: CapacityObjective
}

export interface Arrow {
    from: string
    to: string
    hypothesis: string
}

export interface CoreValues {
    values: string[]
    synthesised: boolean
    rationale: string
}

export interface StrategyMap {
    vision: VisionStatement
    mission: MissionStatement
    valueProposition: ValuePropositionClassification
    strategicPriorities: StrategicPriority[]
    financial: { objectives: FinancialObjective[] }
    customer: { objectives: CustomerObjective[] }
    internalProcesses: { themes: InternalProcessTheme[] }
    organizationalCapacity: OrganizationalCapacityPerspective
    arrows: Arrow[]
    coreValues: CoreValues
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

/**
 * Recently-Deleted admin UI types (Phase 2 of soft-delete recovery).
 *
 * The `/api/admin/recently-deleted` endpoint returns a flat list of
 * tombstoned scans + analyses for the caller's org within a time
 * window. The backend denormalises actor name and parent-tombstone
 * status at read time so the client renders without joining.
 *
 * The `/api/admin/restore` endpoint accepts a mixed-type id list and
 * returns a `restored` / `failed` breakdown per id.
 */
export type RecentlyDeletedRecordType = 'analysis' | 'scan'

/** Reasons a restore attempt can fail per-id. */
export type RestoreFailureReason = 'not_found' | 'ttl_expired'

export interface RecentlyDeletedActor {
    id: string
    name: string
}

export interface RecentlyDeletedRecord {
    id: string
    type: RecentlyDeletedRecordType
    /** Company name for analyses; source URL for scans. */
    displayName: string
    /** Set on analyses; null for scans (which have no parent). */
    scanId: string | null
    /** ISO 8601; consumed by `<RelativeTime>`. */
    deletedAt: string
    /** null when the actor is unknown (pre-tombstone records or missing). */
    deletedBy: RecentlyDeletedActor | null
    /**
     * True when this is an analysis whose parent scan is also
     * tombstoned. UI surfaces a warning + "restore parent too?" hint.
     */
    parentTombstoned: boolean
}

export interface RecentlyDeletedResponse {
    records: RecentlyDeletedRecord[]
}

export interface RestoreFailure {
    id: string
    reason: RestoreFailureReason
}

export interface RestoreResponse {
    restored: string[]
    failed: RestoreFailure[]
}

/** Time-window literal that maps to the backend's `?window=` query param. */
export type RecentlyDeletedWindow = '24h' | '7d' | '30d' | '90d'
