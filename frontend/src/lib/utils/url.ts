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

/**
 * Normalise free-text URL input from a user into a canonical form the
 * scrape pipeline can fetch, or return a friendly error string.
 *
 * Permissive on input form, strict on shape — Chrome's omnibox is the
 * mental model:
 *
 *   `example.com`             → `https://example.com`
 *   `www.example.com`         → `https://www.example.com`
 *   `https://example.com/`    → `https://example.com/` (unchanged)
 *   `http://example.com`      → `http://example.com` (unchanged — caller's choice to keep http)
 *   `example`                 → error (no dot, cannot be a hostname)
 *   `   `                     → error (empty)
 *   `not a url`               → error (URL constructor rejects)
 *
 * The scheme is auto-prepended only if absent — we never replace an
 * explicit `http://` with `https://` because some intranet / staging
 * targets legitimately need plain HTTP. The backend scrape pipeline is
 * the source of truth for whether a URL actually resolves; this
 * function only catches obvious shape errors so the user doesn't
 * submit `www.foo.com` and get a generic browser-native rejection.
 *
 * Returns either `{ url }` with the normalised string, or `{ error }`
 * with a single user-facing sentence (no trailing period, sentence
 * case) ready to render in the form's error slot.
 */
export function normalizeUserUrl(input: string): { url: string } | { error: string } {
    const trimmed = input.trim()
    if (trimmed === '') {
        return { error: 'Please enter a website URL (e.g. example.com)' }
    }

    // Auto-prepend https:// only if NO scheme is present. We detect by
    // looking for `://` rather than `^https?:` so weird input like
    // `://foo.com` still gets normalised rather than coerced into
    // `https://://foo.com`. Anything with a scheme already (including
    // `http://`, `ftp://`, etc.) is left for URL constructor to judge.
    const hasExplicitScheme = trimmed.includes('://')
    const withScheme = hasExplicitScheme ? trimmed : `https://${trimmed}`

    let parsed: URL
    try {
        parsed = new URL(withScheme)
    } catch {
        return { error: 'Please enter a website URL (e.g. example.com)' }
    }

    // Soft hostname-shape check is ONLY applied when we auto-prepended
    // the scheme. The intent of the check is to catch bare-word input
    // like ``foo`` or ``localhost`` that the URL constructor accepts as
    // a valid host but the scrape pipeline can't fetch on the public
    // internet. When the user has already typed an explicit scheme
    // (``http://...``, ``https://...``), we trust them — they may be
    // pointing at a docker-DNS hostname (``http://ai-mock:8080/...`` in
    // E2E setups), an IP address, or an intranet host. Skipping the
    // guard here keeps the validator out of the way of legitimate
    // power-user input without weakening the rejection of typos in the
    // common path.
    if (!hasExplicitScheme && !parsed.hostname.includes('.')) {
        return { error: 'Please enter a website URL (e.g. example.com)' }
    }

    return { url: parsed.toString() }
}
