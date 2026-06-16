import { redirect } from 'next/navigation'
import { getServerSession } from 'next-auth'
import type { Metadata } from 'next'

import { backendFetch } from '@/lib/api/serverToken'
import { authOptions } from '@/lib/auth/authOptions'
import type { ConnectedAppsResponse } from '@/lib/types/api'

import ConnectedAppsView from './ConnectedAppsView'

export const metadata: Metadata = { title: 'Connected Apps — sc0red Services' }

/**
 * Connected Apps — the AI assistants this user has connected to sc0red Services
 * over MCP/OAuth. Per-user (not org-wide): the list is the caller's own OAuth
 * consents, fetched server-side and handed to the client view for the revoke
 * interaction. Any authenticated user can manage their own connections, so —
 * unlike the admin-only settings pages — there is no role gate here.
 */
export default async function ConnectedAppsPage() {
    const session = await getServerSession(authOptions)
    if (!session?.user) {
        redirect('/login')
    }

    let data: ConnectedAppsResponse = { connected_apps: [] }
    try {
        data = await backendFetch<ConnectedAppsResponse>('/api/connected-apps')
    } catch {
        // Prefer an empty list over a hard error — a transient backend hiccup
        // shouldn't 500 the settings flow; the view re-fetches on revoke.
    }

    return <ConnectedAppsView initialApps={data.connected_apps} />
}
