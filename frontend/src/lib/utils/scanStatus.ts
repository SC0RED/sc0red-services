/**
 * Scan-status predicates shared across dashboard + portfolio surfaces.
 *
 * The backend's scan lifecycle has four in-flight statuses
 * (`pending`, `discovering`, `awaiting_confirmation`, `running`) and two
 * terminal ones (`complete`, `failed`). Delete affordances should only
 * surface on terminal scans — deleting a scan mid-flight would race the
 * SQS worker and leave the scan/queue in an inconsistent state.
 *
 * Centralising the set here so the dashboard and the portfolio page
 * gate the delete button on the same definition; otherwise drift is
 * inevitable next time we add a status.
 */

export const IN_FLIGHT_SCAN_STATUSES = ['pending', 'discovering', 'awaiting_confirmation', 'running'] as const

export type InFlightScanStatus = (typeof IN_FLIGHT_SCAN_STATUSES)[number]

/**
 * Returns true when the scan is in a terminal state (`complete` or
 * `failed`) and can therefore be safely deleted. Unknown statuses are
 * treated as terminal — defensive default for forward-compat: a new
 * status the frontend doesn't recognise yet is more likely terminal
 * (the alternative is silently hiding the delete button on every scan
 * after a backend rollout).
 */
export function canDeleteScan(status: string | null | undefined): boolean {
    if (!status) return false
    return !(IN_FLIGHT_SCAN_STATUSES as readonly string[]).includes(status)
}
