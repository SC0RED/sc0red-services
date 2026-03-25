/**
 * Real-time scan progress hook via AppSync WebSocket subscription.
 *
 * Provides instant progress updates alongside HTTP polling fallback.
 * If AppSync is not configured or the WebSocket fails, this hook is
 * a no-op and the caller's existing polling continues unaffected.
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

interface UseScanRealtimeOptions {
    onProgress: (progress: number, label: string) => void
    onComplete: () => void
    onFailed: (error: string) => void
}

export function useScanRealtime(options: UseScanRealtimeOptions): {
    start: (scanId: string) => Promise<boolean>
    stop: () => void
} {
    const optionsRef = useRef(options)
    optionsRef.current = options

    const unsubscribeRef = useRef<(() => void) | null>(null)

    const stop = useCallback(() => {
        if (unsubscribeRef.current) {
            unsubscribeRef.current()
            unsubscribeRef.current = null
        }
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

                            optionsRef.current.onProgress(progress.progress, progress.progressLabel)
                            if (progress.status === 'complete') {
                                optionsRef.current.onComplete()
                            } else if (progress.status === 'failed') {
                                optionsRef.current.onFailed('Analysis failed.')
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
