export type Mode = 'portfolio' | 'standalone'
export type Phase = 'input' | 'analyzing' | 'portfolio_confirm' | 'running'

export interface Company {
    name: string
    url: string
    description: string
    selected: boolean
}

export interface AnalysisSummary {
    id?: string
    analyzedAt?: string | null
    pipelineProgress?: number
    pipelineLabel?: string
    error?: string
}

/**
 * How thoroughly discovery covered the firm's portfolio, mirrored from the
 * backend `discovery_verdict`. `completeness` drives the customer-facing
 * message; `availableActions` (subset of search_deeper / render_site /
 * upload_list) drives which next-step affordances are offered.
 */
export type DiscoveryCompleteness =
    | 'full_site_list'
    | 'partial_site_list'
    | 'site_blocked'
    | 'web_search_subset'
    | 'web_search_exhausted'
    | 'genuinely_empty'

export type DiscoveryAction = 'search_deeper' | 'render_site' | 'upload_list'

export interface DiscoveryVerdict {
    /** How the result was produced (site / web_search / none). Carried for
     *  parity with the backend + future analytics; not rendered today. */
    method: string
    count: number
    completeness: DiscoveryCompleteness
    availableActions: DiscoveryAction[]
}

export interface ScanPollResponse {
    status: string
    progress?: number
    progressLabel?: string
    portfolioCompanies?: Omit<Company, 'selected'>[]
    discoveryVerdict?: DiscoveryVerdict | null
    analyses?: AnalysisSummary[]
    analysisId?: string
    error?: string
}
