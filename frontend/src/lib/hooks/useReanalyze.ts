'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'

import { useToast } from '@/components/ui'
import { useScanRealtime } from '@/lib/hooks/useScanRealtime'
import type { AnalysisData } from '@/lib/types/api'

export interface UseReanalyzeOptions {
    analysisId: string
    /**
     * The currently-rendered `analyzedAt` value. Used as the baseline
     * the polling loop watches: when the API returns a different value
     * we know the re-analysis pipeline finished and the page can
     * refresh.
     */
    analyzedAt: string | undefined
}

export interface UseReanalyzeResult {
    /** Whether a re-analysis is currently in flight. */
    reanalyzing: boolean
    /** Latest progress percentage (0–100). */
    reanalysisProgress: number
    /** Latest progress label string from the pipeline. */
    reanalysisLabel: string
    /** Last error surfaced from the polling loop, if any. */
    documentError: string | null
    /** Manually clear the surfaced error. */
    clearError: () => void
    /** Set/replace the surfaced error from outside the hook. */
    setDocumentError: (message: string | null) => void
    /** Trigger a re-analysis. */
    triggerReanalyze: () => Promise<void>
}

const POLL_MAX_ATTEMPTS = 40
const POLL_INTERVAL_MS = 3000
const POLL_ERROR_TOLERANCE = 3

/**
 * Re-analysis controller hook for the analysis detail screen.
 *
 * Wraps the lifecycle that was previously inlined in
 * `AnalysisDetail.tsx`: kicks off the re-analysis, subscribes to
 * AppSync realtime progress, polls for `analyzedAt` to flip, threads
 * a single loading toast through to success/failure, and aborts
 * cleanly when the user navigates away.
 *
 * Extracted to keep the parent screen under the 360-line file budget
 * and to give the polling logic an independent unit-test surface in a
 * follow-up.
 */
export function useReanalyze({ analysisId, analyzedAt }: UseReanalyzeOptions): UseReanalyzeResult {
    const router = useRouter()
    const toast = useToast()

    const [reanalyzing, setReanalyzing] = useState(false)
    const [reanalysisProgress, setReanalysisProgress] = useState(0)
    const [reanalysisLabel, setReanalysisLabel] = useState('')
    const [documentError, setDocumentError] = useState<string | null>(null)

    const abortControllerRef = useRef<AbortController | null>(null)

    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort()
        }
    }, [])

    const reanalysisRealtime = useScanRealtime({
        onProgress: (progress, label) => {
            setReanalysisProgress((prev) => Math.max(prev, progress))
            if (label) setReanalysisLabel(label)
        },
        onComplete: () => {
            setReanalysisProgress(100)
            setReanalysisLabel('Re-analysis complete!')
            setReanalyzing(false)
            abortControllerRef.current?.abort()
            reanalysisRealtime.stop()
            router.refresh()
        },
        onFailed: (error) => {
            setDocumentError(error)
            setReanalyzing(false)
            reanalysisRealtime.stop()
        },
    })

    const triggerReanalyze = useCallback(async () => {
        setReanalyzing(true)
        setReanalysisProgress(0)
        setReanalysisLabel('')
        setDocumentError(null)
        // Loading toast spans the entire re-analysis lifecycle (poll loop +
        // realtime). Promoted to success/error in place when the polling
        // resolves so there's never a duplicate toast for the same operation.
        const reanalysisToastId = toast.loading('Re-analyzing...')
        const controller = new AbortController()
        abortControllerRef.current = controller
        try {
            const response = await fetch(`/api/analysis/${analysisId}/reanalyze`, {
                method: 'POST',
                signal: controller.signal,
            })
            if (!response.ok) throw new Error('Re-analysis failed')

            const responseData = (await response.json()) as { status: string; scanId?: string }
            const reanalyzeScanId = responseData.scanId

            let realtimeConnected = false
            if (reanalyzeScanId) {
                realtimeConnected = await reanalysisRealtime.start(reanalyzeScanId)
            }

            const originalAnalyzedAt = analyzedAt
            let consecutiveErrors = 0

            for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
                await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
                if (controller.signal.aborted) {
                    // Aborted between intervals — dismiss the loading toast so
                    // it doesn't leak. The outer catch only sees AbortErrors
                    // raised by `await fetch`, not signal-checked early exits.
                    toast.dismiss(reanalysisToastId)
                    return
                }
                try {
                    const pollResponse = await fetch(`/api/analysis/${analysisId}`, {
                        signal: controller.signal,
                    })
                    if (!pollResponse.ok) {
                        consecutiveErrors++
                        if (consecutiveErrors >= POLL_ERROR_TOLERANCE) throw new Error('Polling failed')
                        continue
                    }
                    consecutiveErrors = 0
                    const updated = (await pollResponse.json()) as AnalysisData

                    // Update progress from poll data when realtime is not connected
                    if (!realtimeConnected) {
                        const pollProgress = updated.pipelineProgress ?? 0
                        const pollLabel = updated.pipelineLabel ?? ''
                        if (pollProgress > 0) {
                            setReanalysisProgress((prev) => Math.max(prev, pollProgress))
                        }
                        if (pollLabel) {
                            setReanalysisLabel(pollLabel)
                        }
                    }

                    if (updated.analyzedAt && updated.analyzedAt !== originalAnalyzedAt) {
                        reanalysisRealtime.stop()
                        toast.update(reanalysisToastId, {
                            variant: 'success',
                            message: 'Re-analysis complete',
                        })
                        router.refresh()
                        return
                    }
                } catch (error: unknown) {
                    if (error instanceof DOMException && error.name === 'AbortError') {
                        // Inner catch absorbs the AbortError so the loop's
                        // `return` exits cleanly — but it bypasses the outer
                        // catch's dismiss path. Dismiss explicitly here.
                        toast.dismiss(reanalysisToastId)
                        return
                    }
                    throw error
                }
            }

            // Polling exhausted maxAttempts without observing a fresh
            // analyzedAt — surface as success-with-caveat. The router
            // refresh will pull whatever the backend has on next render.
            reanalysisRealtime.stop()
            toast.update(reanalysisToastId, {
                variant: 'success',
                message: 'Re-analysis queued',
                description: 'Refreshing — results may take a moment to appear.',
            })
            router.refresh()
        } catch (error: unknown) {
            if (error instanceof DOMException && error.name === 'AbortError') {
                toast.dismiss(reanalysisToastId)
                return
            }
            const message = error instanceof Error ? error.message : 'Re-analysis failed'
            toast.update(reanalysisToastId, {
                variant: 'error',
                message: `Re-analysis failed: ${message}`,
            })
            setDocumentError(message)
        } finally {
            setReanalyzing(false)
            setReanalysisProgress(0)
            setReanalysisLabel('')
            abortControllerRef.current = null
        }
    }, [analysisId, analyzedAt, router, reanalysisRealtime, toast])

    const clearError = useCallback(() => setDocumentError(null), [])

    return {
        reanalyzing,
        reanalysisProgress,
        reanalysisLabel,
        documentError,
        clearError,
        setDocumentError,
        triggerReanalyze,
    }
}
