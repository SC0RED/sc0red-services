import { useRef, useEffect, useCallback } from 'react'

import type { Company, ScanPollResponse } from '@/lib/types/scan'

const MIN_INTERVAL_MS = 1000
const MAX_INTERVAL_MS = 15000
const BACKOFF_FACTOR = 2

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
    onProgress: (progress: number, label: string, rawData?: ScanPollResponse) => void
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
        callbacks.onFailed(data.error?.trim() || 'Analysis failed. Please try again.')
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

    callbacks.onProgress(targetProgress, label, data)

    if (data.status === 'complete') {
        stopPolling()
        callbacks.onComplete(data)
    } else if (data.status === 'failed') {
        stopPolling()
        callbacks.onFailed(data.error?.trim() || 'Portfolio analysis failed.')
    }
}

export function useScanPolling(options: UseScanPollingOptions): {
    startPolling: (scanId: string) => void
    stopPolling: () => void
} {
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const intervalRef = useRef(MIN_INTERVAL_MS)
    const lastProgressRef = useRef(-1)
    const optionsRef = useRef(options)
    optionsRef.current = options

    const stopPolling = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current)
            timeoutRef.current = null
        }
        intervalRef.current = MIN_INTERVAL_MS
        lastProgressRef.current = -1
    }, [])

    useEffect(() => {
        return () => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current)
        }
    }, [])

    const startPolling = useCallback(
        (scanId: string) => {
            stopPolling()

            async function poll() {
                try {
                    const response = await fetch(`/api/scan/${scanId}`)
                    if (!response.ok) return
                    const data: ScanPollResponse = await response.json()

                    // Reset interval on progress change
                    const currentProgress = data.progress ?? 0
                    if (currentProgress !== lastProgressRef.current) {
                        intervalRef.current = MIN_INTERVAL_MS
                        lastProgressRef.current = currentProgress
                    } else {
                        // Exponential backoff when no progress change
                        intervalRef.current = Math.min(intervalRef.current * BACKOFF_FACTOR, MAX_INTERVAL_MS)
                    }

                    const currentOptions = optionsRef.current
                    if (currentOptions.mode === 'discovery') {
                        handleDiscoveryPoll(data, currentOptions, stopPolling)
                    } else {
                        handlePortfolioPoll(data, currentOptions, stopPolling)
                    }
                } catch {
                    // Back off on network errors
                    intervalRef.current = Math.min(intervalRef.current * BACKOFF_FACTOR, MAX_INTERVAL_MS)
                }

                // Schedule next poll if not stopped
                if (timeoutRef.current !== null || intervalRef.current === MIN_INTERVAL_MS) {
                    timeoutRef.current = setTimeout(poll, intervalRef.current)
                }
            }

            // Start first poll immediately
            timeoutRef.current = setTimeout(poll, MIN_INTERVAL_MS)
        },
        [stopPolling]
    )

    return { startPolling, stopPolling }
}
