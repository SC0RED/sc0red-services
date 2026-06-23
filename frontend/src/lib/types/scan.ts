export type Mode = 'portfolio' | 'standalone'
export type Phase = 'input' | 'analyzing' | 'portfolio_confirm' | 'running'

/** Where a candidate came from — drives the reliable (site/upload/provided_url)
 *  vs best-effort (web_search) trust marking. Absent on legacy scans.
 *  `site`/`web_search` come from the backend; `upload` is set client-side when
 *  the customer adds/uploads companies; `provided_url` is reserved for Phase 4
 *  (provide-a-reliable-URL) and not yet emitted. */
export type CompanySource = 'site' | 'web_search' | 'upload' | 'provided_url'

export interface Company {
    name: string
    url: string
    description: string
    selected: boolean
    source?: CompanySource
}

/** Map a discovered company to the editable list, pre-selecting it UNLESS it
 *  came from web search — those are best-effort, so the customer opts in. */
export function withDefaultSelection(company: Omit<Company, 'selected'>): Company {
    return { ...company, selected: company.source !== 'web_search' }
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
    /** The firm page site-derived companies were read from — the reliable-source
     *  anchor shown in the banner. "" when nothing came from the site. */
    siteSourceUrl?: string
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
