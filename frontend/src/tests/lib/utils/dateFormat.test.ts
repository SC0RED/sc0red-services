import { describe, it, expect } from 'vitest'

import { formatAbsoluteUTC, parseIsoDate } from '@/lib/utils/dateFormat'

/**
 * Coverage focus: the SSR-safety invariant. These helpers exist to
 * produce timezone-deterministic strings that survive the server →
 * client hydration boundary. The risky behaviour is "would this
 * disagree if run in a different timezone?" — so the tests assert
 * UTC-vs-local correctness directly.
 */

describe('parseIsoDate', () => {
    it('returns a Date for a valid ISO string', () => {
        const result = parseIsoDate('2026-05-05T10:00:00Z')
        expect(result).not.toBeNull()
        expect(result?.toISOString()).toBe('2026-05-05T10:00:00.000Z')
    })

    it('returns null for null input', () => {
        expect(parseIsoDate(null)).toBeNull()
    })

    it('returns null for undefined input', () => {
        expect(parseIsoDate(undefined)).toBeNull()
    })

    it('returns null for an empty string', () => {
        expect(parseIsoDate('')).toBeNull()
    })

    it('returns null for an unparseable string', () => {
        expect(parseIsoDate('not-a-date')).toBeNull()
    })
})

describe('formatAbsoluteUTC', () => {
    it('formats a date as "Mon D, YYYY" in UTC', () => {
        // Pick a date that's UNAMBIGUOUS by testing both extremes:
        // a date where local-vs-UTC could shift the day boundary.
        // 2026-05-05T10:00:00Z is May 5 UTC and May 5 in any non-tropical TZ.
        const date = new Date('2026-05-05T10:00:00Z')
        expect(formatAbsoluteUTC(date)).toBe('May 5, 2026')
    })

    it('uses UTC, not local time, at the day-boundary edge case', () => {
        // 2026-05-05T23:30:00Z: in UTC this is May 5; in PST (UTC-8)
        // the same instant is 15:30 May 5; in UTC+2 (CEST) it's 01:30
        // May 6. The UTC-deterministic helper MUST produce "May 5"
        // regardless of process timezone.
        const date = new Date('2026-05-05T23:30:00Z')
        expect(formatAbsoluteUTC(date)).toBe('May 5, 2026')
    })

    it('uses UTC, not local time, at the other day-boundary edge case', () => {
        // 2026-05-05T00:30:00Z: this instant is May 4 in any negative-
        // offset TZ but May 5 in UTC. Helper must say May 5.
        const date = new Date('2026-05-05T00:30:00Z')
        expect(formatAbsoluteUTC(date)).toBe('May 5, 2026')
    })

    it('formats single-digit day without zero padding', () => {
        const date = new Date('2026-01-03T12:00:00Z')
        expect(formatAbsoluteUTC(date)).toBe('Jan 3, 2026')
    })

    it('produces the right month abbreviation across all 12 months', () => {
        const months = [
            ['2026-01-15T12:00:00Z', 'Jan 15, 2026'],
            ['2026-02-15T12:00:00Z', 'Feb 15, 2026'],
            ['2026-03-15T12:00:00Z', 'Mar 15, 2026'],
            ['2026-04-15T12:00:00Z', 'Apr 15, 2026'],
            ['2026-05-15T12:00:00Z', 'May 15, 2026'],
            ['2026-06-15T12:00:00Z', 'Jun 15, 2026'],
            ['2026-07-15T12:00:00Z', 'Jul 15, 2026'],
            ['2026-08-15T12:00:00Z', 'Aug 15, 2026'],
            ['2026-09-15T12:00:00Z', 'Sep 15, 2026'],
            ['2026-10-15T12:00:00Z', 'Oct 15, 2026'],
            ['2026-11-15T12:00:00Z', 'Nov 15, 2026'],
            ['2026-12-15T12:00:00Z', 'Dec 15, 2026'],
        ] as const
        for (const [iso, expected] of months) {
            expect(formatAbsoluteUTC(new Date(iso))).toBe(expected)
        }
    })
})
