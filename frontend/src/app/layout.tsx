import type { Metadata } from 'next'
import './globals.css'
import SessionWrapper from '@/components/SessionWrapper'
import { ToastProvider } from '@/components/ui'
import RouteProgress from '@/components/ui/RouteProgress'
import WebVitals from '@/components/WebVitals'

export const metadata: Metadata = {
    title: 'Janus — AI Risk & Opportunity Platform',
    description:
        'Identify AI-driven risks and opportunities across your portfolio with actionable intelligence powered by AI',
}

/**
 * Synchronous theme bootstrap. Runs before React hydrates so the user never
 * sees a flash of the wrong palette. Reads the persisted preference from
 * localStorage, falls back to `prefers-color-scheme`, and writes
 * `data-theme="dark"` or `data-theme="light"` to <html>.
 *
 * Safari private mode throws on localStorage access — the try/catch falls
 * through to OS preference. The toggle in Settings still works in-memory.
 *
 * Keep this in lockstep with `useTheme` (frontend/src/lib/hooks/useTheme.ts);
 * both must agree on the storage key (`janus.theme`) and the resolution rules.
 */
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = null;
    try { stored = window.localStorage.getItem('janus.theme'); } catch (_) {}
    var resolved;
    if (stored === 'dark' || stored === 'light') {
      resolved = stored;
    } else {
      var prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
      resolved = prefersLight ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', resolved);
  } catch (_) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`.trim()

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" suppressHydrationWarning>
            <head>
                {/* eslint-disable-next-line react/no-danger */}
                <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
            </head>
            <body>
                <a href="#main" className="skip-to-content">
                    Skip to main content
                </a>
                <RouteProgress />
                <WebVitals />
                <SessionWrapper>
                    <ToastProvider>{children}</ToastProvider>
                </SessionWrapper>
            </body>
        </html>
    )
}
