import type { Metadata } from 'next'
import './globals.css'
import SessionWrapper from '@/components/SessionWrapper'

export const metadata: Metadata = {
    title: 'Janus — AI Risk & Opportunity Platform',
    description: 'Identify AI-driven risks and opportunities across your portfolio with actionable intelligence powered by AI',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body>
                <SessionWrapper>
                    {children}
                </SessionWrapper>
            </body>
        </html>
    )
}
