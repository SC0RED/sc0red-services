/**
 * Real-time scan progress hook via AppSync WebSocket subscription.
 *
 * Provides instant progress updates alongside HTTP polling fallback.
 * If AppSync is not configured or the WebSocket fails, this hook is
 * a no-op and the caller's existing polling continues unaffected.
 *
 * When totalCompanies is provided (portfolio mode), per-company events
 * are aggregated into a single progress/label for the caller.
 */
import { useRef, useEffect, useCallback } from 'react'

import { createAppSyncSubscription, type AppSyncConfig } from '@/lib/appsync/client'

interface ScanProgressEvent {
    onScanProgress: {
        scanId: string
        companyId?: string
        progress: number
        progressLabel: string
        status: string
    }
}

interface CompanyState {
    progress: number
    label: string
    status: string
}

interface UseScanRealtimeOptions {
    totalCompanies?: number
    onProgress: (progress: number, label: string) => void
    onComplete: () => void
    onFailed: (error: string) => void
    /** Called when discovery reaches ``awaiting_confirmation`` (discovery mode only). */
    onAwaitingConfirmation?: () => void
    /** Called when the first company analysis completes (portfolio mode only). */
    onFirstComplete?: () => void
}

function computeAggregatedProgress(
    companyMap: Map<string, CompanyState>,
    totalCompanies: number
): { progress: number; label: string } {
    let done = 0
    let inProgress = 0
    let totalProgress = 0
    let furthestLabel = ''
    let furthestProgress = 0

    for (const state of companyMap.values()) {
        if (state.status === 'complete') {
            done++
            totalProgress += 100
        } else {
            totalProgress += state.progress
            if (state.progress > 0) {
                inProgress++
                if (state.progress > furthestProgress) {
                    furthestProgress = state.progress
                    furthestLabel = state.label
                }
            }
        }
    }

    const averageProgress = totalCompanies > 0 ? Math.round(totalProgress / totalCompanies) : 0

    const parts: string[] = []
    if (done > 0) parts.push(`${done}/${totalCompanies} complete`)
    if (inProgress > 0) parts.push(`${inProgress} in progress`)
    const suffix = parts.length > 0 ? ` (${parts.join(', ')})` : ''

    const baseLabel = furthestLabel || 'Running AI risk assessment...'
    const label = `${baseLabel}${suffix}`

    return { progress: averageProgress, label }
}

export function useScanRealtime(options: UseScanRealtimeOptions): {
    start: (scanId: string) => Promise<boolean>
    stop: () => void
} {
    const optionsRef = useRef(options)
    optionsRef.current = options

    const unsubscribeRef = useRef<(() => void) | null>(null)
    const companyMapRef = useRef<Map<string, CompanyState>>(new Map())
    const hasNotifiedFirstComplete = useRef(false)

    const stop = useCallback(() => {
        hasNotifiedFirstComplete.current = false
        if (unsubscribeRef.current) {
            unsubscribeRef.current()
            unsubscribeRef.current = null
        }
        companyMapRef.current = new Map()
    }, [])

    const start = useCallback(
        async (scanId: string): Promise<boolean> => {
            stop()

            try {
                const response = await fetch('/api/config')
                const config = (await response.json()) as {
                    appsyncEndpoint?: string
                    appsyncApiKey?: string
                }

                if (!config.appsyncEndpoint || !config.appsyncApiKey) return false

                const appSyncConfig: AppSyncConfig = {
                    endpoint: config.appsyncEndpoint,
                    apiKey: config.appsyncApiKey,
                }

                const query = `subscription OnProgress($scanId: String!) {
                    onScanProgress(scanId: $scanId) {
                        scanId companyId progress progressLabel status
                    }
                }`

                const unsubscribe = createAppSyncSubscription(
                    appSyncConfig,
                    query,
                    { scanId },
                    {
                        onData: (data) => {
                            const event = data as unknown as ScanProgressEvent
                            const progress = event.onScanProgress
                            if (!progress) return

                            const { totalCompanies } = optionsRef.current

                            if (totalCompanies && totalCompanies > 0 && progress.companyId) {
                                // Portfolio mode: aggregate per-company state
                                companyMapRef.current.set(progress.companyId, {
                                    progress: progress.progress,
                                    label: progress.progressLabel,
                                    status: progress.status,
                                })

                                const aggregated = computeAggregatedProgress(
                                    companyMapRef.current,
                                    totalCompanies
                                )
                                optionsRef.current.onProgress(aggregated.progress, aggregated.label)

                                // Check completion state
                                let doneCount = 0
                                for (const state of companyMapRef.current.values()) {
                                    if (state.status === 'complete') doneCount++
                                }

                                // First company done → caller can navigate early
                                if (doneCount >= 1 && !hasNotifiedFirstComplete.current) {
                                    hasNotifiedFirstComplete.current = true
                                    optionsRef.current.onFirstComplete?.()
                                }

                                // All companies done
                                if (doneCount >= totalCompanies) {
                                    optionsRef.current.onComplete()
                                }

                                // Check if any company failed
                                if (progress.status === 'failed') {
                                    // Individual company failure — don't fail whole portfolio
                                    // The complete check above will handle it when all are done
                                }
                            } else {
                                // Standalone / discovery mode: pass through raw progress
                                optionsRef.current.onProgress(progress.progress, progress.progressLabel)
                                if (progress.status === 'complete') {
                                    optionsRef.current.onComplete()
                                } else if (progress.status === 'awaiting_confirmation') {
                                    // Portfolio discovery terminal state — caller must
                                    // fetch the scan record to read the companies list.
                                    optionsRef.current.onAwaitingConfirmation?.()
                                } else if (progress.status === 'failed') {
                                    optionsRef.current.onFailed('Analysis failed.')
                                }
                            }
                        },
                        onError: () => {
                            // Subscription failed — polling fallback continues
                        },
                        onClose: () => {
                            // Connection closed — polling fallback continues
                        },
                    }
                )

                unsubscribeRef.current = unsubscribe
                return true
            } catch {
                // Config fetch failed — polling fallback continues
                return false
            }
        },
        [stop]
    )

    useEffect(() => {
        return () => stop()
    }, [stop])

    return { start, stop }
}
