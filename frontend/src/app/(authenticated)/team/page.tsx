import { redirect } from 'next/navigation'
import { getServerSession } from 'next-auth'

import { authOptions } from '@/lib/auth/authOptions'
import { backendFetch } from '@/lib/api/serverToken'
import TeamView from './TeamView'

interface Member {
    id: string
    email: string
    name: string
    role: string
}

interface PendingInvitation {
    id: string
    email: string
    role: string
    status: string
    invitedAt: string
}

interface MembersResponse {
    members: Member[]
    pendingInvitations: PendingInvitation[]
}

export default async function TeamPage() {
    const session = await getServerSession(authOptions)
    if (!session?.user || session.user.role !== 'admin') {
        redirect('/dashboard')
    }

    let data: MembersResponse = { members: [], pendingInvitations: [] }
    try {
        data = await backendFetch<MembersResponse>('/api/org/members')
    } catch {
        // Will show empty state
    }

    return <TeamView initialMembers={data.members} initialInvitations={data.pendingInvitations} />
}
