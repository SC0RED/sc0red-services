/**
 * AppSync subscription for the on-demand strategy-map worker (per the
 * `strategy-map-on-demand` spec).
 *
 * The worker pushes events on the same `onScanProgress` channel the
 * analysis pipeline uses, distinguished by the `status` field
 * (`strategy_map_complete` / `strategy_map_failed` / `strategy_map_progress`)
 * and the `companyId` field (= analysis_id). This hook:
 *
 *   1. Subscribes to AppSync filtered server-side by `scanId`.
 *   2. Client-side filters events to those carrying our `analysisId` in
 *      the `companyId` field AND a strategy-map status.
 *   3. Routes `strategy_map_complete` to `onComplete` (caller re-fetches
 *      the analysis), `strategy_map_failed` to `onFailed`,
 *      `strategy_map_progress` to `onProgress(percentage, label)`.
 *   4. Maintains a sliding-window inactivity heartbeat (default 600 s).
 *      EVERY matching event resets the timer, so as long as the worker
 *      is reporting progress the timer never fires. When the window
 *      DOES elapse without an event, `onTimeout` fires once but the
 *      subscription stays alive so a late event can still drive the
 *      slot to a terminal state — the caller's `onTimeout` typically
 *      does a `router.refresh()` as a sanity check while the
 *      subscription continues to listen.
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
    /** Fired when an in-flight `strategy_map_progress` event arrives — used
     *  to drive a moving progress bar inside the generating placeholder
     *  instead of a static spinner. ``progress`` is a 0-100 integer. */
    onProgress?: (progress: number, label: string) => void
    /** Fired if no event arrives within ``timeoutMs`` of the LAST event
     *  (sliding window). Distinct from ``onComplete`` / ``onFailed``,
     *  which terminate the subscription. ``onTimeout`` is a heartbeat
     *  miss — caller refetches the analysis as a sanity check; the
     *  subscription keeps running so a late event can still arrive. */
    onTimeout?: () => void
    /** Sliding-window heartbeat in ms. Default 600 s — comfortably
     *  exceeds today's worst-case ~120s generation while still bounded
     *  enough to recover from genuinely-dropped subscriptions. Each
     *  inbound event resets the timer; only true silence triggers
     *  ``onTimeout``. */
    timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 600_000

/**
 * Sliding-window inactivity timer. Cleared + re-armed on every event
 * received via the ``onData`` handler. Fires ``onTimeout`` when the
 * window elapses with no events. Behaviour on fire depends on whether
 * a live subscription is set up:
 *
 *   - ``hasSubscription=true`` (happy path): stay armed. AppSync
 *     delivery can resume after a transient network blip; the caller's
 *     ``onTimeout`` typically does a ``router.refresh()`` as a
 *     cold-load fallback while the subscription stays alive.
 *   - ``hasSubscription=false`` (config fetch failed / AppSync not
 *     configured): tear down. No subscription means no recovery from
 *     this side; the cold-load is the only escape hatch.
 */
function scheduleFallbackTimeout(args: {
    timeoutRef: MutableRefObject<ReturnType<typeof setTimeout> | null>
    optionsRef: MutableRefObject<UseStrategyMapSubscriptionOptions | null>
    stop: () => void
    timeoutMs: number | undefined
    hasSubscription: boolean
}): void {
    const ms = args.timeoutMs ?? DEFAULT_TIMEOUT_MS
    args.timeoutRef.current = setTimeout(() => {
        args.optionsRef.current?.onTimeout?.()
        if (!args.hasSubscription) {
            args.stop()
        }
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
                // Config fetch failed — no subscription will be created,
                // so this fallback is the slot's only escape hatch.
                // ``hasSubscription=false`` → timer firing tears down.
                scheduleFallbackTimeout({
                    timeoutRef: timeoutHandleRef,
                    optionsRef,
                    stop,
                    timeoutMs: options.timeoutMs,
                    hasSubscription: false,
                })
                return false
            }

            if (!config.appsyncEndpoint || !config.appsyncApiKey) {
                // AppSync intentionally not configured (local dev / test).
                // Same fallback-timeout treatment as the fetch-failure
                // branch — the slot recovers via cold-load.
                scheduleFallbackTimeout({
                    timeoutRef: timeoutHandleRef,
                    optionsRef,
                    stop,
                    timeoutMs: options.timeoutMs,
                    hasSubscription: false,
                })
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

            const resetInactivityTimer = (): void => {
                if (timeoutHandleRef.current) {
                    clearTimeout(timeoutHandleRef.current)
                    timeoutHandleRef.current = null
                }
                scheduleFallbackTimeout({
                    timeoutRef: timeoutHandleRef,
                    optionsRef,
                    stop,
                    timeoutMs: options.timeoutMs,
                    hasSubscription: true,
                })
            }

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

                        // Reset the sliding-window heartbeat: we're hearing
                        // from the worker, no reason to fall back yet.
                        resetInactivityTimer()

                        if (progress.status === 'strategy_map_complete') {
                            optionsRef.current?.onComplete()
                            stop()
                        } else if (progress.status === 'strategy_map_failed') {
                            optionsRef.current?.onFailed()
                            stop()
                        } else if (progress.status === 'strategy_map_progress') {
                            optionsRef.current?.onProgress?.(progress.progress, progress.progressLabel)
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
            scheduleFallbackTimeout({
                timeoutRef: timeoutHandleRef,
                optionsRef,
                stop,
                timeoutMs: options.timeoutMs,
                hasSubscription: true,
            })
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
