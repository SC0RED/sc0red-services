import { redirect, notFound } from 'next/navigation'
import { getServerSession } from 'next-auth'

import { BackendError } from '@/lib/api/errors'
import { backendFetch } from '@/lib/api/serverToken'
import { authOptions } from '@/lib/auth/authOptions'
import type { AnalysisData } from '@/lib/types/api'

import AnalysisDetail from './AnalysisDetail'

export default async function AnalysisPage({ params }: { params: { analysisId: string } }) {
    const session = await getServerSession(authOptions)
    if (!session) redirect('/login')

    try {
        const data = await backendFetch<AnalysisData>(`/api/analysis/${params.analysisId}`)
        return <AnalysisDetail data={data} analysisId={params.analysisId} />
    } catch (error: unknown) {
        if (error instanceof BackendError && error.status === 404) notFound()
        throw error
    }
}
