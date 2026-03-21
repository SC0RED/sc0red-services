import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'

import { authOptions } from '@/lib/auth/authOptions'
import { backendFetch } from '@/lib/api/serverToken'
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
    } catch {
        return <div style={{ padding: '2rem', color: 'var(--risk-critical)' }}>Scan not found</div>
    }

    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            <DashboardSidebar />
            <main
                style={{ flex: 1, marginLeft: 'var(--sidebar-width)', padding: '2rem', maxWidth: '1200px' }}
            >
                <PortfolioView scanId={params.scanId} initialScan={scan} />
            </main>
        </div>
    )
}
