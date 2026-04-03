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

export interface ScanPollResponse {
    status: string
    progress?: number
    progressLabel?: string
    portfolioCompanies?: Omit<Company, 'selected'>[]
    analyses?: AnalysisSummary[]
    analysisId?: string
}
