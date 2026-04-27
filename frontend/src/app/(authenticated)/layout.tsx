import DashboardSidebar from '@/components/DashboardSidebar'
import GlobalShortcuts from '@/components/GlobalShortcuts'
import { Breadcrumbs } from '@/components/ui'

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
    return (
        <>
            <DashboardSidebar />
            <main id="main" tabIndex={-1} className="page-content">
                <Breadcrumbs />
                {children}
            </main>
            <GlobalShortcuts />
        </>
    )
}
