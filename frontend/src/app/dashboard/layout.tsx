import type { Metadata } from 'next'
import DashboardProviders from './providers'

export const metadata: Metadata = { title: 'Dashboard — Janus' }

export default function Layout({ children }: { children: React.ReactNode }) {
    return <DashboardProviders>{children}</DashboardProviders>
}
