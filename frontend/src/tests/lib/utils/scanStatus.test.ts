import { describe, it, expect } from 'vitest'

import { canDeleteScan, displayedCompanyCount, IN_FLIGHT_SCAN_STATUSES } from '@/lib/utils/scanStatus'

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

describe('displayedCompanyCount', () => {
    it('terminal complete scan with empty completedCount uses totalCompanies', () => {
        // The bug we're fixing: dashboard cell rendered 0 because the
        // record's `completed_count` is unset, while `total_companies`
        // (set at confirm time) holds the cascade truth.
        expect(
            displayedCompanyCount({
                status: 'complete',
                completedCount: 0,
                totalCompanies: 6,
            })
        ).toBe(6)
    })

    it('terminal failed scan uses totalCompanies even when partial completedCount exists', () => {
        // Failed scans had some companies finish before the failure;
        // the cell should reflect the confirmed total, not the partial.
        expect(
            displayedCompanyCount({
                status: 'failed',
                completedCount: 4,
                totalCompanies: 6,
            })
        ).toBe(6)
    })

    it('in-flight running scan uses completedCount (the running counter)', () => {
        // Live progress UX: rendering totalCompanies would freeze the
        // cell at the final value before companies actually finish.
        expect(
            displayedCompanyCount({
                status: 'running',
                completedCount: 3,
                totalCompanies: 6,
            })
        ).toBe(3)
    })

    it('in-flight discovering scan with no totalCompanies yet renders 0', () => {
        // Brand-new scan, totalCompanies is unset until confirm. The
        // user should see 0/0 (nothing started yet), not undefined.
        expect(
            displayedCompanyCount({
                status: 'discovering',
                completedCount: 0,
                totalCompanies: undefined,
            })
        ).toBe(0)
    })

    it('in-flight awaiting_confirmation scan renders 0 when both fields missing', () => {
        // Locks in "every in-flight status uses completedCount" without
        // letting a future fourth in-flight status accidentally pick up
        // a different cell value.
        expect(
            displayedCompanyCount({
                status: 'awaiting_confirmation',
                completedCount: 0,
                totalCompanies: undefined,
            })
        ).toBe(0)
    })

    it('missing status falls through to the defensive default of 0', () => {
        // canDeleteScan returns false for missing status, so we fall
        // into the in-flight branch and read completedCount → ?? 0.
        expect(displayedCompanyCount({})).toBe(0)
    })

    it('uses ?? not ||, so a real 0 totalCompanies on terminal scan does NOT fall through', () => {
        // Subtle correctness check. A scan that confirmed with 0
        // companies (an empty PE firm portfolio, say) and finished
        // should render 0, not whatever completedCount happens to be.
        expect(
            displayedCompanyCount({
                status: 'complete',
                completedCount: 5, // would be wrong if `||` fell through
                totalCompanies: 0,
            })
        ).toBe(0)
    })
})
