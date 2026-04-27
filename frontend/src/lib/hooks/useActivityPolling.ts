'use client'

import { useEffect, useRef, useState } from 'react'

import type { ActivityEvent, ActivityEventsResponse } from '@/lib/types/api'

const POLL_INTERVAL_MS = 30_000

interface UseActivityPollingResult {
    events: ActivityEvent[]
    /** True until the first fetch resolves. After that, persistent across polls. */
    loading: boolean
    /**
     * Set when a poll fails. Cleared automatically on the next successful
     * poll. Surfaced for observability, not as a UI affordance — analytics
     * is best-effort, polling drops are silent to the user.
     */
    error: Error | null
}

/**
 * Polls `GET /api/activity` every 30 seconds and exposes the latest event
 * list. Mounting starts a single interval; unmounting stops it.
 *
 * Network failures are absorbed (logged, not thrown) so the activity
 * panel doesn't render an error state every time the user's connection
 * blips. Stale data is preferred to a noisy error surface for this
 * channel.
 *
 * Race-safety: each fetch carries a generation counter; only the most
 * recent in-flight request is allowed to commit results to state. This
 * prevents an out-of-order resolution where a slow request started
 * earlier overwrites a faster request started later.
 *
 * Used by `<ActivityPanel>` (Tier 2 §5).
 */
export function useActivityPolling(): UseActivityPollingResult {
    const [events, setEvents] = useState<ActivityEvent[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<Error | null>(null)

    // Generation counter for race-safe result commits.
    const generationRef = useRef(0)

    useEffect(() => {
        let cancelled = false

        async function poll(): Promise<void> {
            const myGeneration = ++generationRef.current
            try {
                const response = await fetch('/api/activity', { credentials: 'include' })
                if (cancelled || myGeneration !== generationRef.current) return
                if (!response.ok) {
                    throw new Error(`Activity poll failed: ${response.status}`)
                }
                const payload: ActivityEventsResponse = await response.json()
                if (cancelled || myGeneration !== generationRef.current) return
                setEvents(payload.events)
                setError(null)
            } catch (caught) {
                if (cancelled || myGeneration !== generationRef.current) return
                setError(caught instanceof Error ? caught : new Error(String(caught)))
            } finally {
                if (!cancelled && myGeneration === generationRef.current) {
                    setLoading(false)
                }
            }
        }

        void poll()
        const interval = window.setInterval(() => {
            void poll()
        }, POLL_INTERVAL_MS)

        return () => {
            cancelled = true
            window.clearInterval(interval)
        }
    }, [])

    return { events, loading, error }
}
