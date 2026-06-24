/**
 * Post-authentication redirect helpers shared by the login + signup pages.
 *
 * The MCP "Connect this app" flow sends an unauthenticated user from the OAuth
 * consent page (`/oauth/authorize`) to login/signup with the full consent URL
 * as `callbackUrl`, so consent can resume after they authenticate.
 */

/**
 * Resolve where to send the user after a successful login/signup.
 *
 * Only same-origin RELATIVE paths are honored — the value must start with a
 * single `/`. Absolute URLs and protocol-relative `//host` values are rejected
 * (open-redirect guard) and fall back to the dashboard.
 */
export function resolvePostAuthPath(callbackUrl: string | null | undefined): string {
    if (!callbackUrl || !callbackUrl.startsWith('/') || callbackUrl.startsWith('//')) {
        return '/dashboard'
    }
    return callbackUrl
}

/**
 * Build a link to the other auth page that carries the current `callbackUrl`
 * forward, so switching between login and signup mid-consent doesn't drop the
 * return URL. The destination page sanitizes the value on use, so it is safe to
 * forward verbatim.
 */
export function authPathWithCallback(basePath: string, callbackUrl: string | null | undefined): string {
    if (!callbackUrl) {
        return basePath
    }
    return `${basePath}?callbackUrl=${encodeURIComponent(callbackUrl)}`
}
