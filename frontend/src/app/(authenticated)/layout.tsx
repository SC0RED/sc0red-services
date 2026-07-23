import DashboardSidebar from '@/components/DashboardSidebar'
import GlobalShortcuts from '@/components/GlobalShortcuts'
import { Breadcrumbs } from '@/components/ui'
import { ShortcutsUiProvider } from '@/components/ui/ShortcutsUi'

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
    return (
        <ShortcutsUiProvider>
            <DashboardSidebar />
            <main id="main" tabIndex={-1} className="page-content">
                <Breadcrumbs />
                {children}
            </main>
            <GlobalShortcuts />
        </ShortcutsUiProvider>
    )
}
