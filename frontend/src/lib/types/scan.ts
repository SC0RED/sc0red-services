export type Mode = 'portfolio' | 'standalone'
export type Phase = 'input' | 'analyzing' | 'portfolio_confirm' | 'running'

/** Where a candidate came from — drives the reliable (site/upload/provided_url)
 *  vs best-effort (web_search) trust marking. Absent on legacy scans.
 *  `site`/`web_search` come from the backend; `upload` is set client-side when
 *  the customer adds/uploads companies; `provided_url` is reserved for Phase 4
 *  (provide-a-reliable-URL) and not yet emitted. */
export type CompanySource = 'site' | 'web_search' | 'upload' | 'provided_url'

/** Current vs exited holding, when the firm's site exposes it (e.g. a WordPress
 *  status taxonomy). `realized` companies are shown but default-deselected — the
 *  portfolio analysis targets current holdings. Absent/'' ⇒ unknown ⇒ treated as
 *  current/selectable. Set by the backend wp-json discovery rung. */
export type CompanyStatus = 'current' | 'realized' | ''

export interface Company {
    name: string
    url: string
    description: string
    selected: boolean
    source?: CompanySource
    status?: CompanyStatus
}

/** A company can only be analyzed if it has an http(s) URL — mirrors the
 *  backend's confirm-scan check. URL-less rows must not be selectable, or they'd
 *  be counted in "Analyze N" and then silently dropped at confirm. */
export function hasAnalyzableUrl(url: string): boolean {
    return url.startsWith('http://') || url.startsWith('https://')
}

/** Map a discovered company to the editable list, pre-selecting it UNLESS it
 *  came from web search (best-effort → customer opts in), it has no URL to
 *  analyze (selecting it would silently drop at confirm), or it's a realized
 *  (exited) holding (analysis targets the current portfolio → customer opts in). */
export function withDefaultSelection(company: Omit<Company, 'selected'>): Company {
    return {
        ...company,
        selected:
            company.source !== 'web_search' && hasAnalyzableUrl(company.url) && company.status !== 'realized',
    }
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

/** Which source actually produced the list — a post-discovery label from the
 *  backend `classify_delivery_mechanism`. Orthogonal to `completeness`: it
 *  explains the *why* behind a thin/empty result (e.g. `opaque_shell` ⇒ the
 *  firm renders its list client-side and we couldn't read it). "" for verdicts
 *  persisted before the field existed. */
export type DeliveryMechanism =
    | 'unreachable'
    | 'static_listing'
    | 'structured_endpoint'
    | 'embedded_json'
    | 'ai_extracted'
    | 'opaque_shell'
    | 'no_portfolio_found'
    | 'site_listing'

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
    /** Post-discovery delivery-mechanism label; drives the optional "why" hint
     *  in the banner for thin/empty results. "" for older verdicts. */
    deliveryMechanism?: DeliveryMechanism | ''
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
