'use client'

import { useState, useRef, useCallback, type FormEvent } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

import { useCompanyList } from '@/lib/hooks/useCompanyList'
import { useScanPolling } from '@/lib/hooks/useScanPolling'
import { useScanRealtime } from '@/lib/hooks/useScanRealtime'
import type { Mode, Phase, Company, ScanPollResponse, DiscoveryVerdict } from '@/lib/types/scan'
import { hasAnalyzableUrl, withDefaultSelection } from '@/lib/types/scan'
import { normalizeUserUrl } from '@/lib/utils/url'

/** Fetch a scan record for navigation/transition; null on any failure so
 *  callers fall back to polling or minimal data. */
async function fetchScanResponse(scanId: string): Promise<ScanPollResponse | null> {
    try {
        const response = await fetch(`/api/scan/${scanId}`)
        if (response.ok) return (await response.json()) as ScanPollResponse
    } catch {
        /* network error — caller falls back */
    }
    return null
}

/**
 * Owns the new-scan orchestration: phase state, the discovery/portfolio polling
 * + realtime wiring, and every customer action (start, confirm, search deeper,
 * provide-a-URL). The page consumes this and just renders the phase components.
 */
export function usePortfolioScanFlow() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const initialMode = (searchParams.get('type') as Mode) || 'portfolio'

    const [mode, setMode] = useState<Mode>(initialMode)
    const [url, setUrl] = useState('')
    const [phase, setPhase] = useState<Phase>('input')
    const [error, setError] = useState('')
    const [progress, setProgress] = useState(0)
    const [progressLabel, setProgressLabel] = useState('')
    const [scanId, setScanId] = useState('')
    const {
        companies,
        replace: replaceCompanies,
        toggle: handleCompanyToggle,
        addOne: handleAddCompany,
        addMany: handleAddCompanies,
    } = useCompanyList()
    const [verdict, setVerdict] = useState<DiscoveryVerdict | null>(null)
    const scanIdRef = useRef('')
    const hasNavigatedToPortfolio = useRef(false)
    const phaseRef = useRef<Phase>('input')

    const handleProgress = useCallback((newProgress: number, label: string) => {
        setProgress((prev) => Math.max(prev, newProgress))
        if (label) setProgressLabel(label)
    }, [])

    const handleDiscoveryComplete = useCallback(
        (data: ScanPollResponse) => {
            setProgress(100)
            setProgressLabel('Analysis complete!')
            const analysis = data.analyses?.[0]
            // Guard: backend may skip awaiting_confirmation and complete a portfolio directly.
            if (mode === 'portfolio') {
                router.push(`/portfolio/${scanId}`)
            } else if (analysis?.error) {
                setError(`Analysis failed: ${analysis.error}`)
                setPhase('input')
            } else if (analysis?.id) {
                router.push(`/analysis/${analysis.id}`)
            } else {
                setError('Analysis completed but no results were returned.')
                setPhase('input')
            }
        },
        [mode, scanId, router]
    )

    const handlePortfolioComplete = useCallback(
        (_data: ScanPollResponse) => {
            if (hasNavigatedToPortfolio.current) return
            hasNavigatedToPortfolio.current = true
            setProgress(100)
            setProgressLabel('Portfolio analysis complete!')
            router.push(`/portfolio/${scanId}`)
        },
        [scanId, router]
    )

    const handleFailed = useCallback((errorMessage: string) => {
        setError(errorMessage)
        setPhase('input')
    }, [])

    const handleAwaitingConfirmation = useCallback(
        (discoveredCompanies: Company[], discoveredVerdict?: DiscoveryVerdict | null) => {
            replaceCompanies(discoveredCompanies)
            setVerdict(discoveredVerdict ?? null)
            setPhase('portfolio_confirm')
        },
        [replaceCompanies]
    )

    const discoveryPolling = useScanPolling({
        mode: 'discovery',
        onAwaitingConfirmation: handleAwaitingConfirmation,
        onComplete: handleDiscoveryComplete,
        onFailed: handleFailed,
        onProgress: handleProgress,
    })

    const discoveryRealtime = useScanRealtime({
        onProgress: handleProgress,
        onComplete: async () => {
            // AppSync told us it's complete — fetch full data for navigation.
            const data = await fetchScanResponse(scanIdRef.current)
            handleDiscoveryComplete(data ?? { status: 'complete' })
        },
        onAwaitingConfirmation: async () => {
            // Read the scan record to transition; fall back to polling on failure.
            const data = await fetchScanResponse(scanIdRef.current)
            if (data) {
                const discoveredCompanies = (data.portfolioCompanies ?? []).map(withDefaultSelection)
                handleAwaitingConfirmation(discoveredCompanies, data.discoveryVerdict)
                return
            }
            discoveryPolling.startPolling(scanIdRef.current)
        },
        onFailed: handleFailed,
    })

    const selectedCount = companies.filter((c) => c.selected).length

    const handlePortfolioProgress = useCallback(
        (newProgress: number, label: string, rawData?: ScanPollResponse) => {
            handleProgress(newProgress, label)

            // Navigate as soon as the first company completes (phaseRef, not
            // phase state, to avoid a stale-closure read).
            if (
                !hasNavigatedToPortfolio.current &&
                phaseRef.current === 'running' &&
                rawData?.analyses?.some((a) => a.analyzedAt)
            ) {
                hasNavigatedToPortfolio.current = true
                router.push(`/portfolio/${scanIdRef.current}`)
            }
        },
        [handleProgress, router]
    )

    const portfolioPolling = useScanPolling({
        mode: 'portfolio',
        totalCompanies: selectedCount,
        onComplete: handlePortfolioComplete,
        onFailed: handleFailed,
        onProgress: handlePortfolioProgress,
    })

    const portfolioRealtime = useScanRealtime({
        totalCompanies: selectedCount,
        onProgress: handleProgress,
        onFirstComplete: () => {
            // First company done via AppSync — navigate immediately.
            if (!hasNavigatedToPortfolio.current && phaseRef.current === 'running') {
                hasNavigatedToPortfolio.current = true
                router.push(`/portfolio/${scanIdRef.current}`)
            }
        },
        onComplete: async () => {
            // All companies done via AppSync — fetch full data for navigation.
            if (hasNavigatedToPortfolio.current) return
            const data = await fetchScanResponse(scanIdRef.current)
            handlePortfolioComplete(data ?? { status: 'complete' })
        },
        onFailed: handleFailed,
    })

    async function handleSubmit(e: FormEvent) {
        e.preventDefault()
        setError('')

        // Validate before flipping to `analyzing` (inline error, no UI flash);
        // also auto-prepends `https://` (Diagnostic Tool Feedback #1).
        const normalized = normalizeUserUrl(url)
        if ('error' in normalized) {
            setError(normalized.error)
            return
        }

        setPhase('analyzing')
        setProgress(5)
        setProgressLabel(mode === 'portfolio' ? 'Finding portfolio companies...' : 'Starting analysis...')

        try {
            const res = await fetch('/api/scan/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: normalized.url, type: mode }),
            })

            const data = await res.json()
            if (!res.ok) {
                setError(data.error || 'Analysis failed. Please try again.')
                setPhase('input')
                return
            }
            setScanId(data.scanId)
            scanIdRef.current = data.scanId

            if (data.status === 'complete') {
                setProgress(100)
                setProgressLabel('Analysis complete!')
                if (mode === 'standalone' && data.analysisId) {
                    router.push(`/analysis/${data.analysisId}`)
                } else {
                    router.push(`/portfolio/${data.scanId}`)
                }
                return
            }

            if (data.status === 'awaiting_confirmation' && data.portfolioCompanies) {
                const companiesWithSelect = (data.portfolioCompanies as Omit<Company, 'selected'>[]).map(
                    withDefaultSelection
                )
                handleAwaitingConfirmation(companiesWithSelect, data.discoveryVerdict)
                return
            }

            const realtimeConnected = await discoveryRealtime.start(data.scanId)
            if (!realtimeConnected) {
                discoveryPolling.startPolling(data.scanId)
            }
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : 'Network error — please check your connection and try again.'
            )
            setPhase('input')
        }
    }

    async function confirmPortfolio() {
        // Stop discovery hooks first — they share the scanId subscription, and a
        // per-company status=failed would otherwise reset the page to input.
        discoveryPolling.stopPolling()
        discoveryRealtime.stop()

        // Gate on analyzability too: only send rows that are selected AND have a
        // URL, so what we dispatch matches the "Analyze N" count and the backend
        // never silently drops a selected-but-url-less row.
        const selected = companies.filter((c) => c.selected && hasAnalyzableUrl(c.url))
        phaseRef.current = 'running'
        setPhase('running')
        setProgress(5)
        setProgressLabel('Queuing company analyses...')

        try {
            const res = await fetch(`/api/scan/${scanId}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ companies: selected }),
            })

            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                setError(data.error || 'Failed to start portfolio analysis')
                setPhase('portfolio_confirm')
                return
            }

            setProgress(10)
            setProgressLabel(`Analyzing companies... (0/${selected.length} complete)`)
            const realtimeConnected = await portfolioRealtime.start(scanId)
            if (!realtimeConnected) {
                portfolioPolling.startPolling(scanId)
            }
        } catch {
            setError('Network error — could not start portfolio analysis. Please try again.')
            setPhase('portfolio_confirm')
        }
    }

    // Shared body for the additive escalations ("Search deeper" / provide-a-URL):
    // POST, then re-enter the discovery loop (worker transitions back through
    // `discovering` to `awaiting_confirmation`); on failure, return to confirm.
    async function runDiscoveryEscalation(
        path: string,
        init: RequestInit,
        startLabel: string,
        failLabel: string,
        networkLabel: string
    ) {
        setError('')
        setProgress(5)
        setProgressLabel(startLabel)
        setPhase('analyzing')
        try {
            const res = await fetch(`/api/scan/${scanId}/${path}`, init)
            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                setError(data.error || failLabel)
                setPhase('portfolio_confirm')
                return
            }
            const realtimeConnected = await discoveryRealtime.start(scanId)
            if (!realtimeConnected) {
                discoveryPolling.startPolling(scanId)
            }
        } catch {
            setError(networkLabel)
            setPhase('portfolio_confirm')
        }
    }

    function handleSearchDeeper() {
        return runDiscoveryEscalation(
            'deepen',
            { method: 'POST' },
            'Searching deeper for more companies…',
            'Could not search deeper. Please try again.',
            'Network error — could not search deeper. Please try again.'
        )
    }

    function handleProvideSourceUrl(sourceUrl: string) {
        return runDiscoveryEscalation(
            'source-url',
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sourceUrl }),
            },
            'Reading the page you provided…',
            'Could not read that page. Please try again.',
            'Network error — could not read that page. Please try again.'
        )
    }

    return {
        mode,
        url,
        phase,
        error,
        progress,
        progressLabel,
        companies,
        verdict,
        setMode,
        setUrl,
        handleSubmit,
        handleCompanyToggle,
        handleAddCompany,
        handleAddCompanies,
        handleSearchDeeper,
        handleProvideSourceUrl,
        confirmPortfolio,
        resetToInput: () => setPhase('input'),
    }
}
