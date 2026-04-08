import type { Metadata } from 'next'
import './globals.css'
import SessionWrapper from '@/components/SessionWrapper'
import RouteProgress from '@/components/ui/RouteProgress'
import WebVitals from '@/components/WebVitals'

export const metadata: Metadata = {
    title: 'Janus — AI Risk & Opportunity Platform',
    description:
        'Identify AI-driven risks and opportunities across your portfolio with actionable intelligence powered by AI',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body>
                <a href="#main" className="skip-to-content">
                    Skip to main content
                </a>
                <RouteProgress />
                <WebVitals />
                <SessionWrapper>{children}</SessionWrapper>
            </body>
        </html>
    )
}
