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
    const withScheme = trimmed.includes('://') ? trimmed : `https://${trimmed}`

    let parsed: URL
    try {
        parsed = new URL(withScheme)
    } catch {
        return { error: 'Please enter a website URL (e.g. example.com)' }
    }

    // Soft hostname-shape check: a bare-domain hostname must contain at
    // least one dot. Catches `localhost`-style and typos like `foo` that
    // URL accepts as a valid host but the scrape pipeline can't fetch.
    // `localhost` itself is intentionally rejected — this is the
    // customer-facing scan input, not a dev tool.
    if (!parsed.hostname.includes('.')) {
        return { error: 'Please enter a website URL (e.g. example.com)' }
    }

    return { url: parsed.toString() }
}
