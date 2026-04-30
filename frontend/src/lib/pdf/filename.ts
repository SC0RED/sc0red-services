/**
 * Filename helpers for the PDF export Content-Disposition header.
 *
 * The user-facing filename is derived from the company name + analysis date:
 *   "Acme Corp - AI Risk Report - 2026-04-30.pdf"
 *
 * Sanitisation rules (matching the spec scenarios):
 *   - Strip slashes, colons, and other characters invalid in filenames
 *   - Collapse runs of whitespace to a single space
 *   - Trim
 *   - Cap to 80 chars total (including the date suffix and extension)
 *   - UTF-8 preserved via `filename*=UTF-8''…` per RFC 5987
 */

const FILENAME_MAX_CHARS = 80
const SUFFIX = ' - AI Risk Report'
const EXTENSION = '.pdf'

/**
 * Disallowed characters in filenames across Windows / macOS / Linux. We
 * intentionally do NOT strip whitespace control chars (`\t`, `\n`, `\r`)
 * here because the whitespace-collapse step below maps them onto a single
 * space — stripping them first would silently remove the word boundary.
 */
const INVALID_CHAR_RE = /[\x00-\x08\x0b\x0c\x0e-\x1f<>:"/\\|?*\x7f]/g

/**
 * Format `yyyy-MM-dd` from a Date or ISO string. Defaults to "today" in UTC
 * so two clients in different timezones get the same filename for the same
 * render (the API route runs in Lambda where local time isn't meaningful).
 */
export function formatAnalysisDate(input?: Date | string): string {
    const date = input ? new Date(input) : new Date()
    if (Number.isNaN(date.getTime())) return formatAnalysisDate()
    const yyyy = date.getUTCFullYear()
    const mm = String(date.getUTCMonth() + 1).padStart(2, '0')
    const dd = String(date.getUTCDate()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd}`
}

/**
 * Sanitised company name suitable for embedding in a filename. Falls back
 * to "Analysis" when the input is empty or all-invalid characters.
 */
export function sanitiseCompanyName(raw: string): string {
    const stripped = raw.replace(INVALID_CHAR_RE, '').replace(/\s+/g, ' ').trim()
    return stripped || 'Analysis'
}

/**
 * Build the user-facing filename and the wire-format `Content-Disposition`
 * header. The header carries both `filename=` (ASCII fallback) and
 * `filename*=UTF-8''…` (per RFC 5987) so non-ASCII company names survive
 * the round-trip through the browser's download flow.
 */
export function buildPdfFilename(companyName: string, analysisDate?: Date | string): string {
    const company = sanitiseCompanyName(companyName)
    const date = formatAnalysisDate(analysisDate)

    // Reserve space for the suffix + date + extension; truncate the company
    // segment so the whole filename stays under FILENAME_MAX_CHARS.
    const tail = `${SUFFIX} - ${date}${EXTENSION}`
    const maxCompany = Math.max(1, FILENAME_MAX_CHARS - tail.length)
    const companyClipped = company.length > maxCompany ? company.slice(0, maxCompany).trim() : company

    return `${companyClipped}${tail}`
}

export function buildContentDisposition(filename: string): string {
    // ASCII fallback strips non-ASCII chars; the UTF-8 form preserves them.
    const ascii = filename.replace(/[^\x20-\x7e]/g, '_').replace(/"/g, '')
    const utf8 = encodeURIComponent(filename)
    return `attachment; filename="${ascii}"; filename*=UTF-8''${utf8}`
}
