import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'

import { backendFetch } from '@/lib/api/serverToken'
import { authOptions } from '@/lib/auth/authOptions'
import type { AnalysisData } from '@/lib/types/api'
import ComparisonView from '@/components/comparison/ComparisonView'

interface ComparePageProps {
    searchParams: Promise<{ ids?: string }>
}

export default async function ComparePage({ searchParams }: ComparePageProps) {
    const session = await getServerSession(authOptions)

    if (!session?.user?.orgId) {
        redirect('/login')
    }

    const params = await searchParams
    const idsParam = params.ids ?? ''
    const ids = idsParam.split(',').filter(Boolean)

    if (ids.length < 2 || ids.length > 3) {
        redirect('/analyses')
    }

    const analyses = await Promise.all(
        ids.map(async (id) => {
            try {
                return await backendFetch<AnalysisData>(`/api/analysis/${id}`)
            } catch {
                return null
            }
        })
    )

    const validAnalyses = analyses.filter((a): a is AnalysisData => a !== null)

    if (validAnalyses.length < 2) {
        redirect('/analyses')
    }

    return <ComparisonView analyses={validAnalyses} />
}
