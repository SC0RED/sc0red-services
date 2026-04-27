'use client'

import { format, formatDistanceToNow } from 'date-fns'
import { useEffect, useMemo, useState } from 'react'

interface RelativeTimeProps {
    /** ISO 8601 timestamp string (or null/undefined). */
    value: string | null | undefined
    /** Rendered when `value` is missing or invalid. Defaults to em-dash. */
    fallback?: string
}

const MONTH_ABBREV = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
] as const

/**
 * Renders a timestamp as a relative-time label ("3 hours ago", "just now").
 *
 * Hydration-safe by design: on SSR + the very first client paint the label
 * is a UTC-based absolute date (e.g. "Apr 27, 2026"), formatted manually so
 * server and client produce identical HTML regardless of process timezone.
 * After mount, a `useEffect` swaps the label to a relative phrase and
 * re-ticks every minute.
 *
 * The `<time>` element exposes the full local-time absolute via the
 * `title` attribute, so hovering reveals the precise timestamp without a
 * custom popover.
 *
 * Used everywhere a timestamp is shown to the user (analyses table, dashboard
 * recent items, etc). See `webapp-ux-foundations-tier2` §4.
 */
export default function RelativeTime({ value, fallback = '—' }: RelativeTimeProps) {
    // Memoise the parsed Date so it's referentially stable between renders
    // when `value` hasn't changed. Without this, every render produces a
    // new Date object and the effect's dependency array would have to use
    // a primitive workaround like `date?.getTime()` (and silence the
    // exhaustive-deps lint rule). Memoising lets us depend on `date`
    // directly and keeps the lint signal honest.
    const date = useMemo(() => parseDate(value), [value])

    // Seed `label` with the deterministic absolute on SSR / first paint.
    // After mount, the effect overwrites it with the relative phrase.
    // Lazy initializer so `formatAbsoluteUTC` only runs on the first render
    // — `useState(value)` evaluates `value` on every render but only uses
    // the result once.
    const [label, setLabel] = useState(() => (date ? formatAbsoluteUTC(date) : ''))

    useEffect(() => {
        if (!date) return
        const update = () => setLabel(formatRelative(date))
        update()
        // Re-tick once a minute. 60s is granular enough for the phrasing
        // changes ("a minute ago" → "2 minutes ago") without burning a
        // requestAnimationFrame loop.
        const interval = setInterval(update, 60_000)
        return () => clearInterval(interval)
    }, [date])

    if (!date) return <>{fallback}</>

    const fullAbsolute = format(date, 'PPpp') // e.g. "Apr 27, 2026 at 3:45:22 PM"
    return (
        <time dateTime={date.toISOString()} title={fullAbsolute}>
            {label}
        </time>
    )
}

function parseDate(value: string | null | undefined): Date | null {
    if (!value) return null
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date
}

/**
 * Deterministic absolute formatter used only for the SSR / pre-mount label.
 * Manually composed in UTC so server (any TZ) and client (any TZ) produce
 * identical strings — avoids React hydration mismatches.
 */
function formatAbsoluteUTC(date: Date): string {
    return `${MONTH_ABBREV[date.getUTCMonth()]} ${date.getUTCDate()}, ${date.getUTCFullYear()}`
}

/**
 * Relative phrase used after mount.
 *
 * `formatDistanceToNow` returns "less than a minute ago" for sub-minute
 * diffs, which feels too verbose for the recent case. We override anything
 * under 30 seconds with "just now" and let date-fns handle the rest.
 *
 * Negative diffs (timestamp in the future — clock skew) fall through to
 * `formatDistanceToNow`, which prefixes "in" appropriately.
 */
function formatRelative(date: Date): string {
    const diffMs = Date.now() - date.getTime()
    if (diffMs >= 0 && diffMs < 30_000) return 'just now'
    return formatDistanceToNow(date, { addSuffix: true })
}
