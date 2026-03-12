import { getServerSession } from 'next-auth'

import { authOptions } from '@/lib/auth/authOptions'
import { backendFetch } from '@/lib/api/serverToken'
import DashboardSidebar from '@/components/DashboardSidebar'
import PortfolioView from './PortfolioView'

interface ScanAnalysis {
    id: string
    companyName: string
    companyUrl: string
    industry: string
    overallRiskScore: number | null
    riskTier: string | null
    error: string | null
    analyzedAt: string | null
}

interface ScanData {
    status: string
    progress: number
    type: string
    portfolioCompanies: Array<{ name: string; url: string }>
    analyses: ScanAnalysis[]
}

export default async function PortfolioPage({ params }: { params: { scanId: string } }) {
    const session = await getServerSession(authOptions)
    const orgId = session?.user?.orgId

    if (!session || !orgId) {
        const { redirect } = await import('next/navigation')
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
