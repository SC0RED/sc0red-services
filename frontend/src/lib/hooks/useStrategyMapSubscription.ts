/**
 * AppSync subscription for the on-demand strategy-map worker (per the
 * `strategy-map-on-demand` spec).
 *
 * The worker pushes events on the same `onScanProgress` channel the
 * analysis pipeline uses, distinguished by the `status` field
 * (`strategy_map_complete` / `strategy_map_failed`) and the `companyId`
 * field (= analysis_id). This hook:
 *
 *   1. Subscribes to AppSync filtered server-side by `scanId`.
 *   2. Client-side filters events to those carrying our `analysisId` in
 *      the `companyId` field AND a strategy-map status.
 *   3. Routes `strategy_map_complete` to `onComplete` (caller re-fetches
 *      the analysis), `strategy_map_failed` to `onFailed`.
 *   4. Implements a 90-second client-side fallback timer: if no event
 *      arrives within 90s of subscribing, fires a one-shot fallback
 *      callback so the caller can do a `GET /api/analysis/{id}` to
 *      check whether the worker completed despite a dropped subscription.
 *
 * If AppSync isn't configured (local dev, tests), the hook is a no-op —
 * the caller's natural cold-load + refresh behaviour keeps working.
 */
import { useCallback, useEffect, useRef, type MutableRefObject } from 'react'

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

interface UseStrategyMapSubscriptionOptions {
    analysisId: string
    scanId: string
    /** Fired when an `strategy_map_complete` event arrives for this analysis. */
    onComplete: () => void
    /** Fired when an `strategy_map_failed` event arrives for this analysis. */
    onFailed: () => void
    /** Fired once if no event arrives within ``timeoutMs`` of subscribing.
     *  Caller should do a one-shot `GET /api/analysis/{id}` to check whether
     *  the worker completed despite a dropped subscription. */
    onTimeout?: () => void
    /** Client-side fallback window before `onTimeout` fires. Default 90 s. */
    timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 90_000

/**
 * Schedules the 90-second client-side fallback. Mutates the timer ref
 * so `stop()` can clear it. Called from three branches inside `start()`:
 *   - happy path (subscription created)
 *   - config-fetch failure (no subscription)
 *   - AppSync not configured (no subscription)
 * In all three the caller wants the slot to eventually recover via a
 * `router.refresh()` triggered by `onTimeout`, so we schedule the timer
 * uniformly rather than duplicate the body inline.
 */
function scheduleFallbackTimeout(
    timeoutRef: MutableRefObject<ReturnType<typeof setTimeout> | null>,
    optionsRef: MutableRefObject<UseStrategyMapSubscriptionOptions | null>,
    stop: () => void,
    timeoutMs: number | undefined
): void {
    const ms = timeoutMs ?? DEFAULT_TIMEOUT_MS
    timeoutRef.current = setTimeout(() => {
        optionsRef.current?.onTimeout?.()
        stop()
    }, ms)
}

export function useStrategyMapSubscription(): {
    start: (options: UseStrategyMapSubscriptionOptions) => Promise<boolean>
    stop: () => void
} {
    const unsubscribeRef = useRef<(() => void) | null>(null)
    const timeoutHandleRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const optionsRef = useRef<UseStrategyMapSubscriptionOptions | null>(null)

    const stop = useCallback(() => {
        if (unsubscribeRef.current) {
            unsubscribeRef.current()
            unsubscribeRef.current = null
        }
        if (timeoutHandleRef.current) {
            clearTimeout(timeoutHandleRef.current)
            timeoutHandleRef.current = null
        }
        optionsRef.current = null
    }, [])

    const start = useCallback(
        async (options: UseStrategyMapSubscriptionOptions): Promise<boolean> => {
            stop()
            optionsRef.current = options

            // Stage 1 — fetch AppSync config. The only EXPECTED failure
            // mode here is "AppSync isn't configured in this env" (local
            // dev, tests, or transient network blip during config fetch);
            // a hard failure isn't fatal because the worker still
            // completes server-side and the page-level cold-load reflects
            // it. Caught narrowly so unrelated programming errors (a bug
            // in the subscription factory below) propagate normally.
            let config: { appsyncEndpoint?: string; appsyncApiKey?: string }
            try {
                const response = await fetch('/api/config')
                config = (await response.json()) as {
                    appsyncEndpoint?: string
                    appsyncApiKey?: string
                }
            } catch {
                // Config fetch failed — caller's fallback timer is set
                // below by the timeout schedule, but only AFTER the
                // subscription is created. With no subscription path,
                // schedule the timeout directly so the slot still
                // recovers via the parent's `onTimeout` → refresh.
                scheduleFallbackTimeout(timeoutHandleRef, optionsRef, stop, options.timeoutMs)
                return false
            }

            if (!config.appsyncEndpoint || !config.appsyncApiKey) {
                // AppSync intentionally not configured (local dev / test).
                // Same fallback-timeout treatment as the fetch-failure
                // branch — the slot recovers via cold-load.
                scheduleFallbackTimeout(timeoutHandleRef, optionsRef, stop, options.timeoutMs)
                return false
            }

            // Stage 2 — create the subscription. Errors here are
            // programming errors (bad query, bad config shape, library
            // bug) and MUST propagate so the slot doesn't lock into a
            // permanent generating state with no recovery. The caller
            // (effect inside AnalysisDetail) wraps `start()` in
            // `void startStrategyMapSubscription(...)`, so an
            // uncaught rejection becomes an unhandled promise rejection
            // that's visible in CloudWatch / browser dev tools — the
            // intended fail-fast surface for a bug.
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
                { scanId: options.scanId },
                {
                    onData: (data) => {
                        const event = data as unknown as ScanProgressEvent
                        const progress = event.onScanProgress
                        if (!progress) return

                        // Client-side filter: only act on events for THIS analysis.
                        // The worker pushes with `companyId = analysis_id`.
                        if (progress.companyId !== optionsRef.current?.analysisId) {
                            return
                        }

                        if (progress.status === 'strategy_map_complete') {
                            optionsRef.current?.onComplete()
                            stop()
                        } else if (progress.status === 'strategy_map_failed') {
                            optionsRef.current?.onFailed()
                            stop()
                        }
                        // Other statuses (`running`, `complete`, etc.) belong to the
                        // analysis pipeline and are ignored here.
                    },
                    onError: () => {
                        // Subscription failed — fallback timer + cold-load handle it.
                    },
                    onClose: () => {
                        // Connection closed — fallback timer handles recovery.
                    },
                }
            )

            unsubscribeRef.current = unsubscribe
            scheduleFallbackTimeout(timeoutHandleRef, optionsRef, stop, options.timeoutMs)
            return true
        },
        [stop]
    )

    // Cleanup subscription + timer on unmount.
    useEffect(() => {
        return () => stop()
    }, [stop])

    return { start, stop }
}
