import { getServerSession } from 'next-auth'
import { notFound, redirect } from 'next/navigation'

import { authOptions } from '@/lib/auth/authOptions'
import { backendFetch } from '@/lib/api/serverToken'
import { BackendError } from '@/lib/api/errors'
import type { ScanData } from '@/lib/types/api'
import DashboardSidebar from '@/components/DashboardSidebar'
import PortfolioView from './PortfolioView'

export default async function PortfolioPage({ params }: { params: { scanId: string } }) {
    const session = await getServerSession(authOptions)
    const orgId = session?.user?.orgId

    if (!session || !orgId) {
        redirect('/login')
    }

    let scan: ScanData
    try {
        scan = await backendFetch<ScanData>(`/api/scan/${params.scanId}`)
    } catch (error: unknown) {
        if (error instanceof BackendError && error.status === 404) notFound()
        throw error
    }

    return (
        <div className="page-layout">
            <DashboardSidebar />
            <main id="main" tabIndex={-1} className="page-content-wide">
                <PortfolioView scanId={params.scanId} initialScan={scan} />
            </main>
        </div>
    )
}
