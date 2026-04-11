import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'

import { backendFetch } from '@/lib/api/serverToken'
import { authOptions } from '@/lib/auth/authOptions'
import type { AnalysisItem } from '@/lib/types/api'
import AnalysesTable from '@/components/AnalysesTable'

export default async function AnalysesPage() {
    const session = await getServerSession(authOptions)

    if (!session?.user?.orgId) {
        redirect('/login')
    }

    const data = await backendFetch<{ analyses: AnalysisItem[] }>('/api/analyses')
    const analyses = data.analyses

    return (
        <>
            <div style={{ marginBottom: '2rem' }}>
                <h1 className="page-title">All Analyses</h1>
                <p style={{ color: 'var(--text-secondary)' }}>
                    Browse all completed company risk assessments
                </p>
            </div>

            <AnalysesTable analyses={analyses} />
        </>
    )
}
