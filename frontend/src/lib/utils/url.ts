/**
 * Strip protocol and trailing slash for a compact, human-readable label.
 * `https://perotjain.com/` → `perotjain.com`
 * `https://www.example.com/firms/123/` → `www.example.com/firms/123`
 *
 * Falls back to the original string when `URL` parsing fails (rare —
 * malformed URLs from a database column for instance). Used to display
 * scan source URLs in the analysis header, command palette, and other
 * surfaces where a short identifier reads better than a full URL.
 */
export function prettifyUrl(url: string): string {
    try {
        const parsed = new URL(url)
        return (parsed.host + parsed.pathname).replace(/\/$/, '')
    } catch {
        return url
    }
}
