'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { useToast } from '@/components/ui'

interface ExportPDFButtonProps {
    analysisId: string
    /** Optional className to extend the default `btn btn-secondary` styling. */
    className?: string
}

/**
 * Polling cadence per ``openspec/changes/async-pdf-export-with-cache/``:
 * 2 s for the first 10 polls (~20 s — covers the typical ~13 s render),
 * then 5 s indefinitely. The backend's stale-rendering window is 60 s,
 * so a stuck render naturally terminates the polling loop within ~70 s
 * (the status endpoint returns ``status: 'failed'`` synthetically for
 * stale-rendering records).
 */
const POLL_FAST_INTERVAL_MS = 2_000
const POLL_FAST_COUNT = 10
const POLL_SLOW_INTERVAL_MS = 5_000

/**
 * Hard safety cap on total polling duration. The 60-second stale window
 * means a stuck render returns ``failed`` within ~62 s; a long-tail
 * render that legitimately exceeds that is uncommon. 5 minutes covers
 * the worst case without leaking timers if the user leaves the page
 * loaded indefinitely.
 */
const POLL_MAX_DURATION_MS = 5 * 60 * 1000

/**
 * Consecutive status-endpoint failures we tolerate before giving up.
 * Single transient failures (e.g., one DDB throttle) shouldn't kill the
 * flow, but a sustained outage should surface an error to the user
 * rather than poll silently forever.
 */
const POLL_MAX_CONSECUTIVE_FAILURES = 5

type ButtonState = 'idle' | 'posting' | 'polling'

interface PostExportResponse {
    status: 'ready' | 'rendering' | 'failed'
    url?: string
    generatedAt?: string
    startedAt?: string
    error?: string
}

interface StatusResponse {
    status: 'none' | 'ready' | 'rendering' | 'failed'
    url?: string
    generatedAt?: string
    startedAt?: string
    error?: string
}

/**
 * Trigger a browser download for a presigned S3 URL. The S3 response
 * carries ``Content-Disposition: attachment; filename="<...>"`` via the
 * ``ResponseContentDisposition`` query param the backend set on the
 * presigned URL — that header is authoritative for the download
 * behaviour, so we don't need the ``download`` attribute (which is
 * ignored for cross-origin URLs anyway).
 */
function triggerDownload(presignedUrl: string): void {
    const link = document.createElement('a')
    link.href = presignedUrl
    // ``rel="noopener"`` defends against the (unlikely) case that the
    // presigned URL response renders HTML for some reason — without it,
    // the loaded URL could reference ``window.opener``.
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
}

/**
 * Click handler for "Export PDF". POSTs to ``/api/export/pdf/<id>`` and
 * either redirects to a fresh presigned URL (cached path) or enters a
 * polling state that watches ``/api/export/pdf/<id>/status`` until the
 * backend transitions to ``ready`` / ``failed``.
 */
export default function ExportPDFButton({ analysisId, className }: ExportPDFButtonProps) {
    const [state, setState] = useState<ButtonState>('idle')
    const toast = useToast()

    // Polling state. ``pollTimerRef`` holds the active ``setTimeout`` so
    // unmount + state transitions can clear it. ``loadingToastIdRef``
    // holds the in-flight "Generating PDF…" toast id so we can dismiss
    // it deterministically when polling ends. ``abortRef`` lets the
    // unmount cleanup cancel any in-flight fetch.
    const pollTimerRef = useRef<number | null>(null)
    const loadingToastIdRef = useRef<string | null>(null)
    const abortRef = useRef<AbortController | null>(null)
    const pollStartedAtRef = useRef<number | null>(null)
    const consecutiveFailuresRef = useRef<number>(0)
    const pollCountRef = useRef<number>(0)

    const cleanupPolling = useCallback(() => {
        if (pollTimerRef.current !== null) {
            window.clearTimeout(pollTimerRef.current)
            pollTimerRef.current = null
        }
        if (loadingToastIdRef.current !== null) {
            toast.dismiss(loadingToastIdRef.current)
            loadingToastIdRef.current = null
        }
        abortRef.current?.abort()
        abortRef.current = null
        pollStartedAtRef.current = null
        consecutiveFailuresRef.current = 0
        pollCountRef.current = 0
    }, [toast])

    const reset = useCallback(() => {
        cleanupPolling()
        setState('idle')
    }, [cleanupPolling])

    useEffect(
        () => () => {
            // Unmount: cancel in-flight + clear timers + dismiss toast.
            cleanupPolling()
        },
        [cleanupPolling]
    )

    /**
     * Run one status poll. Schedules the next tick on ``rendering``,
     * exits the loop on ``ready`` / ``failed`` / hard-cap / repeated
     * network failures.
     */
    const pollOnce = useCallback(async () => {
        if (pollStartedAtRef.current === null) return
        if (Date.now() - pollStartedAtRef.current > POLL_MAX_DURATION_MS) {
            toast.error('PDF generation timed out. Please try again.')
            reset()
            return
        }

        pollCountRef.current += 1
        const controller = new AbortController()
        abortRef.current = controller

        let body: StatusResponse | null = null
        try {
            const res = await fetch(`/api/export/pdf/${analysisId}/status`, {
                method: 'GET',
                signal: controller.signal,
            })
            if (!res.ok) {
                throw new Error(`Status check failed (HTTP ${res.status})`)
            }
            body = (await res.json()) as StatusResponse
            consecutiveFailuresRef.current = 0
        } catch (error) {
            if (controller.signal.aborted) return // unmount / explicit reset
            consecutiveFailuresRef.current += 1
            if (consecutiveFailuresRef.current >= POLL_MAX_CONSECUTIVE_FAILURES) {
                const message = error instanceof Error ? error.message : 'Status check failed'
                toast.error(message)
                reset()
                return
            }
        }

        if (body) {
            if (body.status === 'ready' && body.url) {
                triggerDownload(body.url)
                reset()
                return
            }
            if (body.status === 'failed') {
                toast.error(body.error ?? 'PDF generation failed.')
                reset()
                return
            }
            // ``none`` is unexpected — the POST that started this cycle
            // wrote a ``rendering`` row, so the only way to see ``none``
            // is a parallel re-analyse clearing the field. Treat as
            // failure so the user can re-trigger.
            if (body.status === 'none') {
                toast.error('PDF generation was cancelled by re-analyse.')
                reset()
                return
            }
            // status === 'rendering' — keep polling.
        }

        // After ``POLL_FAST_COUNT`` polls have run, schedule the NEXT
        // poll at the slow interval. ``>= POLL_FAST_COUNT`` flips on the
        // 10th-poll boundary so poll 11 is the first one at 5 s.
        const interval =
            pollCountRef.current >= POLL_FAST_COUNT ? POLL_SLOW_INTERVAL_MS : POLL_FAST_INTERVAL_MS
        pollTimerRef.current = window.setTimeout(() => {
            void pollOnce()
        }, interval)
    }, [analysisId, reset, toast])

    const handleClick = useCallback(async () => {
        if (state !== 'idle') return

        // Disable the button synchronously so a fast double-click doesn't
        // fire the handler twice. The state transition to ``posting``
        // renders before the ``await fetch`` yields, which means
        // subsequent clicks bounce off the ``state !== 'idle'`` guard.
        setState('posting')
        const controller = new AbortController()
        abortRef.current = controller

        let postBody: PostExportResponse | null = null
        try {
            const res = await fetch(`/api/export/pdf/${analysisId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: '{}',
                signal: controller.signal,
            })
            // ``res.ok`` is true for any 2xx including 202, so no
            // separate 202 carve-out needed — non-2xx throws.
            if (!res.ok) {
                throw new Error(`PDF export failed (HTTP ${res.status})`)
            }
            postBody = (await res.json()) as PostExportResponse
        } catch (error) {
            if (controller.signal.aborted) return
            const message = error instanceof Error ? error.message : 'Failed to start PDF export'
            toast.error(message)
            reset()
            return
        } finally {
            // Done with this fetch; subsequent ticks may install their own.
            abortRef.current = null
        }

        if (postBody.status === 'ready' && postBody.url) {
            // Cached path — instant redirect, no toast / no polling.
            triggerDownload(postBody.url)
            setState('idle')
            return
        }

        if (postBody.status === 'failed') {
            // Backend reported a synchronous failure (rare — bad config,
            // async-invoke throttled). The polling cycle won't help; show
            // the error directly.
            toast.error(postBody.error ?? 'PDF export failed.')
            setState('idle')
            return
        }

        // Cold path: backend is rendering. Enter polling state.
        loadingToastIdRef.current = toast.loading(
            'Generating PDF…',
            'You can keep working; the download will start automatically.'
        )
        pollStartedAtRef.current = Date.now()
        setState('polling')
        // Kick off the first tick after the fast interval so the backend
        // has a head start on the render.
        pollTimerRef.current = window.setTimeout(() => {
            void pollOnce()
        }, POLL_FAST_INTERVAL_MS)
    }, [analysisId, state, toast, reset, pollOnce])

    const isLoading = state !== 'idle'
    const label = state === 'idle' ? 'Export PDF' : 'Generating PDF…'

    return (
        <button
            type="button"
            onClick={handleClick}
            disabled={isLoading}
            aria-busy={isLoading}
            className={className ?? 'btn btn-secondary'}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
        >
            {isLoading ? (
                <span
                    aria-hidden="true"
                    style={{
                        width: '14px',
                        height: '14px',
                        borderRadius: '50%',
                        border: '2px solid var(--border-subtle)',
                        borderTopColor: 'var(--accent-blue)',
                        animation: 'route-progress 700ms linear infinite',
                    }}
                />
            ) : (
                <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
            )}
            {label}
        </button>
    )
}
