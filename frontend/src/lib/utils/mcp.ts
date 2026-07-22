/**
 * Shared validation for the MCP server address the Connect page shows.
 *
 * The address comes from `/api/config` (`mcpServerUrl`), sourced per-environment
 * from the CDK `mcp_domain`. It is "" when no custom domain is configured (e.g.
 * local dev) and could in principle be malformed, so the Connect page treats
 * anything that is not a well-formed `https://…/mcp` URL as unavailable and
 * disables the URL-dependent controls rather than showing a broken address.
 */
export function isValidMcpUrl(url: string | undefined | null): url is string {
    if (!url) return false
    try {
        const parsed = new URL(url)
        return parsed.protocol === 'https:' && parsed.pathname.endsWith('/mcp')
    } catch {
        return false
    }
}
