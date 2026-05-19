import { notFound } from 'next/navigation'
import { getServerSession } from 'next-auth'
import type { Metadata } from 'next'

import { backendFetch } from '@/lib/api/serverToken'
import { authOptions } from '@/lib/auth/authOptions'
import type { RecentlyDeletedResponse } from '@/lib/types/api'

import RecentlyDeletedView from './RecentlyDeletedView'

export const metadata: Metadata = { title: 'Recently Deleted — sc0red Advisory' }

/**
 * Phase 2 of soft-delete recovery — admin-only page for browsing and
 * restoring tombstoned scans + analyses within the 90-day TTL window.
 *
 * Auth posture (per `recently-deleted-admin-ui` proposal): non-admins
 * get **404**, not 403, so the route doesn't advertise its existence.
 * The sidebar entry is also gated by `adminOnly: true` so they never
 * see the link in the first place — this is the second-line defence.
 *
 * The initial 30-day window list is fetched server-side and passed to
 * the client component for interactivity (window chips, search,
 * selection, restore). Subsequent window changes refetch via the
 * proxy route `/api/admin/recently-deleted?window=...`.
 */
export default async function RecentlyDeletedPage() {
    const session = await getServerSession(authOptions)
    if (!session?.user || session.user.role !== 'admin') {
        notFound()
    }

    let data: RecentlyDeletedResponse = { records: [] }
    try {
        // Default window: 30d (matches the backend default + the chip
        // shown by default in the client).
        data = await backendFetch<RecentlyDeletedResponse>('/api/admin/recently-deleted?window=30d')
    } catch {
        // Empty list rendering is preferable to a hard error here —
        // the page is reachable when the user has admin role; an API
        // hiccup shouldn't 500 the whole settings flow. The client
        // component re-fetches on window change so a transient backend
        // error self-heals on the next interaction.
    }

    return <RecentlyDeletedView initialRecords={data.records} />
}
