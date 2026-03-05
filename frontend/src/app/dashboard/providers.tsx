'use client'

import { SessionProvider } from 'next-auth/react'

export default function DashboardProviders({ children }: { children: React.ReactNode }) {
    return <SessionProvider>{children}</SessionProvider>
}
