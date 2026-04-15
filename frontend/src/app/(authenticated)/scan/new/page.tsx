'use client'

import { useState, useRef, Suspense, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

import ScanInputPhase from '@/components/scan/ScanInputPhase'
import ScanProgressPhase from '@/components/scan/ScanProgressPhase'
import PortfolioConfirmPhase from '@/components/scan/PortfolioConfirmPhase'
import { useScanPolling } from '@/lib/hooks/useScanPolling'
import { useScanRealtime } from '@/lib/hooks/useScanRealtime'
import type { Mode, Phase, Company, ScanPollResponse } from '@/lib/types/scan'

function NewScanContent() {
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
    const [companies, setCompanies] = useState<Company[]>([])
    const scanIdRef = useRef('')

    const handleProgress = useCallback((newProgress: number, label: string) => {
        setProgress((prev) => Math.max(prev, newProgress))
        if (label) setProgressLabel(label)
    }, [])

    const handleDiscoveryComplete = useCallback(
        (data: ScanPollResponse) => {
            setProgress(100)
            setProgressLabel('Analysis complete!')
            // Guard: if backend skips awaiting_confirmation and completes a portfolio scan directly
            if (mode === 'portfolio') {
                router.push(`/portfolio/${scanId}`)
            } else if (data.analyses?.[0]?.id) {
                if (data.analyses[0].error) {
                    setError(`Analysis failed: ${data.analyses[0].error}`)
                    setPhase('input')
                } else {
                    router.push(`/analysis/${data.analyses[0].id}`)
                }
            } else if (data.analyses?.[0]?.error) {
                setError(`Analysis failed: ${data.analyses[0].error}`)
                setPhase('input')
            } else {
                setError('Analysis completed but no results were returned.')
                setPhase('input')
            }
        },
        [mode, scanId, router]
    )

    const handlePortfolioComplete = useCallback(
        (_data: ScanPollResponse) => {
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

    const handleAwaitingConfirmation = useCallback((discoveredCompanies: Company[]) => {
        setCompanies(discoveredCompanies)
        setPhase('portfolio_confirm')
    }, [])

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
            // AppSync told us it's complete — fetch full data for navigation
            try {
                const response = await fetch(`/api/scan/${scanIdRef.current}`)
                if (response.ok) {
                    const data = (await response.json()) as ScanPollResponse
                    handleDiscoveryComplete(data)
                    return
                }
            } catch {
                // Fetch failed — fall through to minimal data
            }
            handleDiscoveryComplete({ status: 'complete' })
        },
        onFailed: handleFailed,
    })

    const selectedCount = companies.filter((c) => c.selected).length

    const portfolioPolling = useScanPolling({
        mode: 'portfolio',
        totalCompanies: selectedCount,
        onComplete: handlePortfolioComplete,
        onFailed: handleFailed,
        onProgress: handleProgress,
    })

    const portfolioRealtime = useScanRealtime({
        totalCompanies: selectedCount,
        onProgress: handleProgress,
        onComplete: async () => {
            // AppSync told us it's complete — fetch full data for navigation
            try {
                const response = await fetch(`/api/scan/${scanIdRef.current}`)
                if (response.ok) {
                    const data = (await response.json()) as ScanPollResponse
                    handlePortfolioComplete(data)
                    return
                }
            } catch {
                // Fetch failed — fall through to minimal data
            }
            handlePortfolioComplete({ status: 'complete' })
        },
        onFailed: handleFailed,
    })

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        setError('')
        setPhase('analyzing')
        setProgress(5)
        setProgressLabel(mode === 'portfolio' ? 'Finding portfolio companies...' : 'Starting analysis...')

        try {
            const res = await fetch('/api/scan/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url.trim(), type: mode }),
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
                    (c) => ({ ...c, selected: true })
                )
                setCompanies(companiesWithSelect)
                setPhase('portfolio_confirm')
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
        const selected = companies.filter((c) => c.selected)
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

    function handleCompanyToggle(index: number, selected: boolean) {
        setCompanies((prev) => prev.map((c, idx) => (idx === index ? { ...c, selected } : c)))
    }

    function handleAddCompany(name: string, url: string) {
        setCompanies((prev) => [...prev, { name, url, description: '', selected: true }])
    }

    return (
        <div style={{ width: '100%', maxWidth: '680px' }}>
            {/* Header */}
            <div style={{ marginBottom: '2rem' }}>
                <h1 className="page-title">New AI Risk Scan</h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    Analyze a company or entire PE portfolio for AI-driven risks and opportunities
                </p>
            </div>

            {phase === 'input' && (
                <ScanInputPhase
                    mode={mode}
                    url={url}
                    error={error}
                    onModeChange={setMode}
                    onUrlChange={setUrl}
                    onSubmit={handleSubmit}
                />
            )}

            {(phase === 'analyzing' || phase === 'running') && (
                <ScanProgressPhase phase={phase} progress={progress} progressLabel={progressLabel} />
            )}

            {phase === 'portfolio_confirm' && (
                <PortfolioConfirmPhase
                    companies={companies}
                    onCompanyToggle={handleCompanyToggle}
                    onAddCompany={handleAddCompany}
                    onConfirm={confirmPortfolio}
                    onReset={() => setPhase('input')}
                />
            )}
        </div>
    )
}

export default function NewScanPage() {
    return (
        <Suspense
            fallback={
                <div
                    style={{
                        display: 'flex',
                        minHeight: '50vh',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    <div
                        style={{
                            width: '32px',
                            height: '32px',
                            border: '3px solid var(--border)',
                            borderTopColor: 'var(--accent-blue)',
                            borderRadius: '50%',
                            animation: 'spin 1s linear infinite',
                        }}
                    />
                </div>
            }
        >
            <NewScanContent />
        </Suspense>
    )
}
