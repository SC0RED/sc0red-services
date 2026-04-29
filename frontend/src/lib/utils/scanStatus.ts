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

/**
 * Subset of a scan record that this helper needs. Kept structural so
 * callers can pass either `ScanItem` (dashboard payload, camelCase) or
 * any future shape with the same three fields.
 */
interface ScanCountFields {
    status?: string | null
    completedCount?: number | null
    totalCompanies?: number | null
}

/**
 * Returns the company count to render in the dashboard's "Recent Scans"
 * Companies cell + the DeleteScanButton's cascade-message scope.
 *
 * The precedence is status-aware on purpose:
 * - **Terminal scans** (`complete` / `failed`, anything not in
 *   `IN_FLIGHT_SCAN_STATUSES`): `totalCompanies ?? completedCount ?? 0`.
 *   `total_companies` is set at confirm time and survives every later
 *   state change — it's the cascade truth for completed scans, even
 *   when `completed_count` is 0 or unset (legacy records pre-counter,
 *   or records modified during a delete/restore cycle).
 * - **In-flight scans**: `completedCount ?? 0`. The user wants to see
 *   the running counter tick upward — rendering the confirmed total
 *   would freeze the cell at the final value before any companies have
 *   actually finished.
 * - **Unknown / missing status**: `0`. Defensive default; matches the
 *   previous `|| 0` floor.
 *
 * Uses `??` (nullish-coalesce) deliberately: a real `0` for
 * `totalCompanies` should NOT fall through to `completedCount`. `??`
 * preserves `0` as a meaningful value, `||` would not.
 *
 * Single source of truth for both consumers — without this helper the
 * dashboard cell and DeleteScanButton inevitably drift, which is the
 * exact bug this fix is closing (per `openspec/changes/fix-dashboard-company-count/`).
 */
export function displayedCompanyCount(scan: ScanCountFields): number {
    if (canDeleteScan(scan.status)) {
        return scan.totalCompanies ?? scan.completedCount ?? 0
    }
    return scan.completedCount ?? 0
}
