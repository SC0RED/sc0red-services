/**
 * Shared configuration constants.
 *
 * NEXT_PUBLIC_* vars are available in both server and client code.
 * Non-prefixed vars are server-side only.
 */

export const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001'

/**
 * Default contact URL for the sc0red CTA banner.
 * Exported so tests can assert against it without hardcoding the literal.
 */
export const SC0RED_CONTACT_URL_DEFAULT = 'https://www.sc0red.com/contact'

/**
 * Resolve the sc0red contact URL.
 *
 * Returns the `NEXT_PUBLIC_SC0RED_CONTACT_URL` env var if set to a non-empty
 * value, otherwise falls back to the default. Empty strings are treated as
 * unset (prevents rendering `href=""`).
 */
export function getSc0redContactUrl(): string {
    const override = process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL
    if (override && override.trim().length > 0) {
        return override
    }
    return SC0RED_CONTACT_URL_DEFAULT
}
