import { describe, it, expect } from 'vitest'

import { canDeleteScan, IN_FLIGHT_SCAN_STATUSES } from '@/lib/utils/scanStatus'

describe('canDeleteScan', () => {
    it('returns true for terminal statuses', () => {
        expect(canDeleteScan('complete')).toBe(true)
        expect(canDeleteScan('failed')).toBe(true)
    })

    it('returns false for every in-flight status', () => {
        // Iterate the source-of-truth list so adding a new in-flight
        // status doesn't silently start allowing delete.
        for (const status of IN_FLIGHT_SCAN_STATUSES) {
            expect(canDeleteScan(status)).toBe(false)
        }
    })

    it('returns false for null or undefined', () => {
        // Defensive: dashboard data sometimes lacks a status (e.g. legacy
        // records). Treat as "not deletable" rather than rendering a
        // delete button on an unknown record.
        expect(canDeleteScan(null)).toBe(false)
        expect(canDeleteScan(undefined)).toBe(false)
        expect(canDeleteScan('')).toBe(false)
    })

    it('returns true for unknown statuses (forward-compat)', () => {
        // A future backend rollout might add a new terminal status
        // before the frontend knows about it. Defaulting to "deletable"
        // is preferable to silently hiding the delete button on every
        // scan after the deploy. This is the inverse posture from the
        // null/undefined case — present-but-unknown is treated as
        // "probably terminal", absent is treated as "not safe".
        expect(canDeleteScan('cancelled')).toBe(true)
        expect(canDeleteScan('archived')).toBe(true)
    })
})
