'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { useToast } from '@/components/ui'

interface ExportPDFButtonProps {
    analysisId: string
    /** Optional className to extend the default `btn btn-secondary` styling. */
    className?: string
}

/**
 * The label shows up after this many ms in flight, signalling "still working
 * — your click did register." Below this threshold the user typically
 * doesn't notice the button changed; above it the silent button feels
 * broken.
 */
const SPINNER_THRESHOLD_MS = 200

/** After this many ms in flight, swap "Generating…" → "Still working…". */
const STILL_WORKING_THRESHOLD_MS = 5_000

/**
 * Hard timeout. The PDF render Lambda has a 30s ceiling; if we haven't
 * heard back by then, surface an error and reset.
 */
const REQUEST_TIMEOUT_MS = 30_000

type ButtonState = 'idle' | 'starting' | 'generating' | 'still-working'

/**
 * Filename extraction from a `Content-Disposition` header. The server is
 * expected to set both `filename=` (ASCII fallback) and `filename*=UTF-8''…`
 * (per RFC 5987) — we prefer the latter for non-ASCII company names.
 *
 * Defensive: if neither parses, fall back to a generic name so the user
 * still gets a download with a sensible extension.
 */
function parseDownloadFilename(header: string | null, fallback: string): string {
    if (!header) return fallback
    const utf8Match = header.match(/filename\*=(?:UTF-8''|utf-8'')([^;]+)/i)
    if (utf8Match) {
        try {
            return decodeURIComponent(utf8Match[1])
        } catch {
            // fall through to ASCII match
        }
    }
    const asciiMatch = header.match(/filename="?([^";]+)"?/i)
    if (asciiMatch) return asciiMatch[1]
    return fallback
}

/**
 * Click handler that fetches `/api/export/pdf/{analysisId}`, builds a Blob
 * URL, and triggers a programmatic download. Replaces the old
 * `<Link target="_blank">` that opened HTML-pretending-to-be-PDF in a new
 * tab — the user now gets a real file.
 */
export default function ExportPDFButton({ analysisId, className }: ExportPDFButtonProps) {
    const [state, setState] = useState<ButtonState>('idle')
    const toast = useToast()

    // Tracks the in-flight request so we can abort it on unmount or when
    // the user mashes the button. AbortController gives us a clean way to
    // cancel both the fetch and the long-running stream the Lambda
    // produces.
    const abortRef = useRef<AbortController | null>(null)

    // Threshold timers for the visual state machine. Refs so multiple
    // clicks reset the same handles instead of leaking stacked timeouts.
    const spinnerTimerRef = useRef<number | null>(null)
    const stillWorkingTimerRef = useRef<number | null>(null)
    const timeoutTimerRef = useRef<number | null>(null)

    const clearTimers = useCallback(() => {
        if (spinnerTimerRef.current !== null) {
            window.clearTimeout(spinnerTimerRef.current)
            spinnerTimerRef.current = null
        }
        if (stillWorkingTimerRef.current !== null) {
            window.clearTimeout(stillWorkingTimerRef.current)
            stillWorkingTimerRef.current = null
        }
        if (timeoutTimerRef.current !== null) {
            window.clearTimeout(timeoutTimerRef.current)
            timeoutTimerRef.current = null
        }
    }, [])

    const reset = useCallback(() => {
        clearTimers()
        abortRef.current = null
        setState('idle')
    }, [clearTimers])

    useEffect(
        () => () => {
            // Unmount: cancel everything in flight so we don't update state
            // on an unmounted component.
            abortRef.current?.abort()
            clearTimers()
        },
        [clearTimers]
    )

    const handleClick = useCallback(async () => {
        if (state !== 'idle') return

        const controller = new AbortController()
        abortRef.current = controller
        setState('starting')

        spinnerTimerRef.current = window.setTimeout(() => {
            setState('generating')
        }, SPINNER_THRESHOLD_MS)

        stillWorkingTimerRef.current = window.setTimeout(() => {
            setState('still-working')
        }, STILL_WORKING_THRESHOLD_MS)

        timeoutTimerRef.current = window.setTimeout(() => {
            controller.abort()
        }, REQUEST_TIMEOUT_MS)

        try {
            const response = await fetch(`/api/export/pdf/${analysisId}`, {
                method: 'GET',
                signal: controller.signal,
            })
            if (!response.ok) {
                throw new Error(`PDF export failed (HTTP ${response.status})`)
            }

            const blob = await response.blob()
            const filename = parseDownloadFilename(
                response.headers.get('content-disposition'),
                `analysis-${analysisId}.pdf`
            )

            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = filename
            // Append + click + remove is the canonical way to programmatically
            // trigger a download in modern browsers; some (Safari) ignore the
            // download attribute on detached elements.
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            URL.revokeObjectURL(url)

            reset()
        } catch (error) {
            if (controller.signal.aborted) {
                // Either the timeout fired or the component unmounted.
                // We discriminate via `timeoutTimerRef.current === null`:
                // the unmount cleanup runs `clearTimers()` (which nulls
                // the ref) BEFORE calling `abort()`, so a null ref means
                // unmount; a non-null ref means the timeout fired itself.
                // (LOW-priority review nit: an explicit `unmountedRef` is
                // cleaner. Deferred — current code is correct + commented,
                // and the discriminator is exercised by the existing test.)
                if (timeoutTimerRef.current === null) {
                    return
                }
                toast.error('PDF export timed out. Please try again.')
            } else {
                const message = error instanceof Error ? error.message : 'Failed to generate PDF'
                toast.error(message)
            }
            reset()
        }
    }, [analysisId, state, toast, reset])

    const isLoading = state !== 'idle'
    const label =
        state === 'still-working' ? 'Still working…' : state === 'idle' ? 'Export PDF' : 'Generating PDF…'

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
