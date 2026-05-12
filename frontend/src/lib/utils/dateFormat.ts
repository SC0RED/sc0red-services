/**
 * Date formatting helpers shared between server-renderable and
 * client-only date displays.
 *
 * Why hand-composed UTC formatting and not `toLocaleDateString` /
 * `formatInTimeZone`?
 * - `toLocaleDateString` is timezone-dependent: a Lambda in UTC and a
 *   client in PST produce different strings for the same instant —
 *   causing React hydration mismatches when used in SSR paths.
 * - The hand-composed UTC variant runs identically on server and
 *   client and produces a stable absolute label that's useful as a
 *   first-paint placeholder (later upgraded to a relative label after
 *   `useEffect` fires, see `RelativeTime.tsx`).
 *
 * The format is intentionally simple ("May 5, 2026"): a buy-side
 * reader transcribing into an investment memo wants an unambiguous
 * absolute date, not a regional-locale variant.
 */

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
 * Format a date as `Mon D, YYYY` in UTC. Server- and client-safe.
 *
 * @example formatAbsoluteUTC(new Date('2026-05-05T10:00:00Z')) // "May 5, 2026"
 */
export function formatAbsoluteUTC(date: Date): string {
    return `${MONTH_ABBREV[date.getUTCMonth()]} ${date.getUTCDate()}, ${date.getUTCFullYear()}`
}

/**
 * Parse an ISO date string. Returns `null` for invalid or empty input
 * so callers can branch on a single nullable value rather than guarding
 * `Number.isNaN(date.getTime())` themselves.
 */
export function parseIsoDate(value: string | null | undefined): Date | null {
    if (!value) return null
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date
}
