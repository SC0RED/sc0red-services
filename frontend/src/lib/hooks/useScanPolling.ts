import { useRef, useEffect, useCallback } from 'react'

import type { Company, ScanPollResponse } from '@/lib/types/scan'

const POLL_INTERVAL_MS = 3000

interface DiscoveryCallbacks {
    mode: 'discovery'
    onAwaitingConfirmation: (companies: Company[]) => void
    onComplete: (data: ScanPollResponse) => void
    onFailed: (error: string) => void
    onProgress: (progress: number, label: string) => void
}

interface PortfolioCallbacks {
    mode: 'portfolio'
    totalCompanies: number
    onComplete: (data: ScanPollResponse) => void
    onFailed: (error: string) => void
    onProgress: (progress: number, label: string) => void
}

type UseScanPollingOptions = DiscoveryCallbacks | PortfolioCallbacks

function handleDiscoveryPoll(
    data: ScanPollResponse,
    callbacks: DiscoveryCallbacks,
    stopPolling: () => void
): void {
    if (typeof data.progress === 'number') {
        callbacks.onProgress(data.progress, data.progressLabel ?? '')
    }

    if (data.status === 'awaiting_confirmation') {
        stopPolling()
        const companies = (data.portfolioCompanies ?? []).map((c) => ({
            ...c,
            selected: true,
        }))
        callbacks.onAwaitingConfirmation(companies)
    } else if (data.status === 'complete') {
        stopPolling()
        callbacks.onComplete(data)
    } else if (data.status === 'failed') {
        stopPolling()
        callbacks.onFailed('Analysis failed. Please try again.')
    }
}

function handlePortfolioPoll(
    data: ScanPollResponse,
    callbacks: PortfolioCallbacks,
    stopPolling: () => void
): void {
    const analysisList = data.analyses ?? []
    const done = analysisList.filter((a) => a.analyzedAt).length
    const inProgressItems = analysisList.filter((a) => !a.analyzedAt && (a.pipelineProgress ?? 0) > 0)

    const doneProgress = done * 100
    const inFlightProgress = inProgressItems.reduce((sum, a) => sum + (a.pipelineProgress ?? 0), 0)
    const avgProgress = (doneProgress + inFlightProgress) / Math.max(callbacks.totalCompanies, 1)
    const targetProgress = 10 + Math.round(avgProgress * 0.85)

    let label: string
    if (done >= callbacks.totalCompanies) {
        label = `Finishing up... (${done}/${callbacks.totalCompanies} complete)`
    } else if (inProgressItems.length > 0) {
        const furthest = inProgressItems.reduce((best, a) =>
            (a.pipelineProgress ?? 0) > (best.pipelineProgress ?? 0) ? a : best
        )
        const stepLabel = furthest.pipelineLabel ?? 'Processing...'
        label = `${stepLabel} (${done}/${callbacks.totalCompanies} complete, ${inProgressItems.length} in progress)`
    } else {
        label = `Analyzing companies... (${done}/${callbacks.totalCompanies} complete)`
    }

    callbacks.onProgress(targetProgress, label)

    if (data.status === 'complete') {
        stopPolling()
        callbacks.onComplete(data)
    } else if (data.status === 'failed') {
        stopPolling()
        callbacks.onFailed('Portfolio analysis failed.')
    }
}

export function useScanPolling(options: UseScanPollingOptions): {
    startPolling: (scanId: string) => void
    stopPolling: () => void
} {
    const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const optionsRef = useRef(options)
    optionsRef.current = options

    const stopPolling = useCallback(() => {
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
        }
    }, [])

    useEffect(() => {
        return () => {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current)
        }
    }, [])

    const startPolling = useCallback(
        (scanId: string) => {
            stopPolling()

            pollIntervalRef.current = setInterval(async () => {
                try {
                    const response = await fetch(`/api/scan/${scanId}`)
                    if (!response.ok) return
                    const data: ScanPollResponse = await response.json()

                    const currentOptions = optionsRef.current
                    if (currentOptions.mode === 'discovery') {
                        handleDiscoveryPoll(data, currentOptions, stopPolling)
                    } else {
                        handlePortfolioPoll(data, currentOptions, stopPolling)
                    }
                } catch {
                    // Silently retry on network errors
                }
            }, POLL_INTERVAL_MS)
        },
        [stopPolling]
    )

    return { startPolling, stopPolling }
}
