import { redirect } from 'next/navigation'
import { getServerSession } from 'next-auth'
import type { Metadata } from 'next'

import { backendFetch } from '@/lib/api/serverToken'
import { authOptions } from '@/lib/auth/authOptions'
import type { ConnectedAppsResponse } from '@/lib/types/api'

import ConnectView from './ConnectView'

export const metadata: Metadata = { title: 'Connect — sc0red Services' }

/**
 * Connect — self-serve MCP onboarding. Shows the per-environment MCP server
 * address, per-client setup instructions, and the user's connected assistants
 * (their OAuth consents) with disconnect. Per-user, not org-wide, so there is no
 * role gate. The server address comes from /api/config (mcpServerUrl); the
 * connected list from /api/connected-apps. Both are fetched server-side; a
 * transient failure degrades to an empty/unavailable state rather than a 500.
 */
export default async function ConnectPage() {
    const session = await getServerSession(authOptions)
    if (!session?.user) {
        redirect('/login')
    }

    let mcpServerUrl = ''
    try {
        const config = await backendFetch<{ mcpServerUrl?: string }>('/api/config')
        mcpServerUrl = config.mcpServerUrl ?? ''
    } catch {
        // Address unavailable → the view renders its unavailable state.
    }

    let apps: ConnectedAppsResponse = { connected_apps: [] }
    try {
        apps = await backendFetch<ConnectedAppsResponse>('/api/connected-apps')
    } catch {
        // Empty list over a hard error — the view re-fetches on disconnect.
    }

    return <ConnectView mcpServerUrl={mcpServerUrl} initialApps={apps.connected_apps} />
}
