'use client'

import { useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

import DashboardSidebar from '@/components/DashboardSidebar'
import SessionWrapper from '@/components/SessionWrapper'

type Mode = 'portfolio' | 'standalone'
type Phase = 'input' | 'analyzing' | 'portfolio_confirm' | 'running'

interface Company {
    name: string
    url: string
    description: string
    selected: boolean
}

function NewScanContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const initialMode = (searchParams.get('type') as Mode) || 'portfolio'

    const [mode, setMode] = useState<Mode>(initialMode)
    const [url, setUrl] = useState('')
    const [phase, setPhase] = useState<Phase>('input')
    const [error, setError] = useState('')
    const [progress, setProgress] = useState(0)
    const [progressLabel, setProgressLabel] = useState('')
    const [scanId, setScanId] = useState('')
    const [companies, setCompanies] = useState<Company[]>([])

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        setError('')
        setPhase('analyzing')
        setProgress(5)
        setProgressLabel('Starting analysis...')

        // Animate progress bar while waiting for long-running request
        const progressInterval = setInterval(() => {
            setProgress((prev) => {
                if (prev >= 85) return prev
                return prev + Math.random() * 3
            })
        }, 2000)

        const stages = [
            'Gathering company intelligence...',
            'Extracting company profile...',
            'Running AI risk assessment...',
            'Generating opportunity recommendations...',
        ]
        let stageIdx = 0
        const stageInterval = setInterval(() => {
            stageIdx = Math.min(stageIdx + 1, stages.length - 1)
            setProgressLabel(stages[stageIdx])
        }, 8000)

        try {
            const res = await fetch('/api/scan/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url.trim(), type: mode }),
            })
            clearInterval(progressInterval)
            clearInterval(stageInterval)

            const data = await res.json()
            if (!res.ok) {
                setError(data.error || 'Analysis failed. Please try again.')
                setPhase('input')
                return
            }
            setScanId(data.scanId)

            // Handle inline response from the new awaited API
            if (data.status === 'complete') {
                setProgress(100)
                setProgressLabel('Analysis complete!')
                if (mode === 'standalone' && data.analysisId) {
                    router.push(`/analysis/${data.analysisId}`)
                } else {
                    router.push(`/portfolio/${data.scanId}`)
                }
                return
            }

            if (data.status === 'awaiting_confirmation' && data.portfolioCompanies) {
                const companiesWithSelect = (data.portfolioCompanies as Omit<Company, 'selected'>[]).map(
                    (c) => ({ ...c, selected: true })
                )
                setCompanies(companiesWithSelect)
                setPhase('portfolio_confirm')
                return
            }

            // Fallback: poll for status if the request returned early
            pollStatus(data.scanId)
        } catch (err) {
            clearInterval(progressInterval)
            clearInterval(stageInterval)
            setError(
                err instanceof Error
                    ? err.message
                    : 'Network error — please check your connection and try again.'
            )
            setPhase('input')
        }
    }

    async function pollStatus(id: string) {
        const stages = [
            'Gathering company intelligence...',
            'Extracting company profile...',
            'Running AI risk assessment...',
            'Generating opportunity recommendations...',
        ]
        let stageIdx = 0

        const interval = setInterval(async () => {
            const res = await fetch(`/api/scan/${id}`)
            if (!res.ok) return
            const data = await res.json()

            setProgress(data.progress || 0)
            stageIdx = Math.min(Math.floor((data.progress / 100) * stages.length), stages.length - 1)
            setProgressLabel(stages[stageIdx])

            if (data.status === 'awaiting_confirmation') {
                clearInterval(interval)
                const companiesWithSelect = (
                    (data.portfolioCompanies as Omit<Company, 'selected'>[] | undefined) ?? []
                ).map((c) => ({ ...c, selected: true }))
                setCompanies(companiesWithSelect)
                setPhase('portfolio_confirm')
            } else if (data.status === 'complete') {
                clearInterval(interval)
                if (mode === 'portfolio') {
                    router.push(`/portfolio/${id}`)
                } else if (data.analyses?.[0]) {
                    router.push(`/analysis/${data.analyses[0].id}`)
                }
            } else if (data.status === 'failed') {
                clearInterval(interval)
                setError('Analysis failed. Please try again.')
                setPhase('input')
            }
        }, 2000)
    }

    async function confirmPortfolio() {
        const selected = companies.filter((c) => c.selected)
        setPhase('running')
        setProgress(25)
        setProgressLabel('Starting portfolio analysis...')

        // Animate progress bar while waiting
        const completed = 0
        const progressInterval = setInterval(() => {
            setProgress((prev) => {
                if (prev >= 90) return prev
                return prev + Math.random() * 2
            })
            setProgressLabel(
                `Analyzing companies... (${Math.min(completed, selected.length)}/${selected.length} complete)`
            )
        }, 5000)

        try {
            const res = await fetch(`/api/scan/${scanId}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ companies: selected }),
            })
            clearInterval(progressInterval)

            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                setError(data.error || 'Failed to start portfolio analysis')
                setPhase('portfolio_confirm')
                return
            }

            // Backend returns 202 — analysis runs async via SQS, poll for completion
            pollRunning(scanId, selected.length)
        } catch {
            clearInterval(progressInterval)
            pollRunning(scanId, selected.length)
        }
    }

    async function pollRunning(id: string, total: number) {
        const interval = setInterval(async () => {
            const res = await fetch(`/api/scan/${id}`)
            if (!res.ok) return
            const data = await res.json()
            const done =
                data.analyses?.filter((a: { analyzed_at?: string | null }) => a.analyzed_at)?.length || 0
            setProgress(25 + Math.round((done / Math.max(total, 1)) * 70))
            setProgressLabel(`Analyzing companies... (${done}/${total} complete)`)

            if (data.status === 'complete') {
                clearInterval(interval)
                router.push(`/portfolio/${id}`)
            } else if (data.status === 'failed') {
                clearInterval(interval)
                setError('Portfolio analysis failed.')
                setPhase('input')
            }
        }, 3000)
    }

    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            <DashboardSidebar />
            <main
                style={{
                    flex: 1,
                    marginLeft: 'var(--sidebar-width)',
                    padding: '2.5rem',
                    display: 'flex',
                    justifyContent: 'center',
                }}
            >
                <div style={{ width: '100%', maxWidth: '680px' }}>
                    {/* Header */}
                    <div style={{ marginBottom: '2rem' }}>
                        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>
                            New AI Risk Scan
                        </h1>
                        <p style={{ color: 'var(--text-secondary)' }}>
                            Analyze a company or entire PE portfolio for AI-driven risks and opportunities
                        </p>
                    </div>

                    {/* Input Phase */}
                    {phase === 'input' && (
                        <div>
                            {/* Mode Toggle */}
                            <div
                                style={{
                                    display: 'grid',
                                    gridTemplateColumns: '1fr 1fr',
                                    gap: '0.75rem',
                                    marginBottom: '1.75rem',
                                }}
                            >
                                {[
                                    {
                                        value: 'portfolio' as Mode,
                                        label: 'PE Portfolio Scan',
                                        desc: 'Auto-discover and analyze all portfolio companies from a PE firm website',
                                        icon: (
                                            <svg
                                                width="20"
                                                height="20"
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="currentColor"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                            >
                                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                                                <circle cx="9" cy="7" r="4" />
                                                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                                                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                                            </svg>
                                        ),
                                    },
                                    {
                                        value: 'standalone' as Mode,
                                        label: 'Single Company',
                                        desc: "Deep-dive analysis of one company's AI risk exposure and opportunities",
                                        icon: (
                                            <svg
                                                width="20"
                                                height="20"
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="currentColor"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                            >
                                                <rect x="3" y="3" width="18" height="18" rx="2" />
                                                <circle cx="12" cy="12" r="4" />
                                            </svg>
                                        ),
                                    },
                                ].map((opt) => (
                                    <button
                                        key={opt.value}
                                        type="button"
                                        onClick={() => setMode(opt.value)}
                                        style={{
                                            padding: '1.25rem',
                                            borderRadius: 'var(--radius-lg)',
                                            border:
                                                mode === opt.value
                                                    ? '2px solid var(--accent-blue)'
                                                    : '1px solid var(--border)',
                                            background:
                                                mode === opt.value
                                                    ? 'rgba(59,123,246,0.06)'
                                                    : 'var(--bg-surface)',
                                            textAlign: 'left',
                                            cursor: 'pointer',
                                            transition: 'all var(--transition-fast)',
                                        }}
                                    >
                                        <div
                                            style={{
                                                color:
                                                    mode === opt.value
                                                        ? 'var(--accent-blue)'
                                                        : 'var(--text-secondary)',
                                                marginBottom: '0.625rem',
                                            }}
                                        >
                                            {opt.icon}
                                        </div>
                                        <div
                                            style={{
                                                fontWeight: 600,
                                                marginBottom: '0.25rem',
                                                color:
                                                    mode === opt.value
                                                        ? 'var(--text-primary)'
                                                        : 'var(--text-secondary)',
                                                fontSize: '0.9375rem',
                                            }}
                                        >
                                            {opt.label}
                                        </div>
                                        <div
                                            style={{
                                                fontSize: '0.8125rem',
                                                color: 'var(--text-tertiary)',
                                                lineHeight: 1.5,
                                            }}
                                        >
                                            {opt.desc}
                                        </div>
                                    </button>
                                ))}
                            </div>

                            <form
                                onSubmit={handleSubmit}
                                style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}
                            >
                                <div className="input-group">
                                    <label className="label" htmlFor="scan-url">
                                        {mode === 'portfolio' ? 'PE Firm Website URL' : 'Company Website URL'}
                                    </label>
                                    <div style={{ position: 'relative' }}>
                                        <span
                                            style={{
                                                position: 'absolute',
                                                left: '1rem',
                                                top: '50%',
                                                transform: 'translateY(-50%)',
                                                color: 'var(--text-tertiary)',
                                            }}
                                        >
                                            <svg
                                                width="16"
                                                height="16"
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="currentColor"
                                                strokeWidth="2"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                            >
                                                <circle cx="12" cy="12" r="10" />
                                                <line x1="2" y1="12" x2="22" y2="12" />
                                                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                                            </svg>
                                        </span>
                                        <input
                                            id="scan-url"
                                            type="url"
                                            className="input"
                                            style={{ paddingLeft: '2.75rem' }}
                                            placeholder={
                                                mode === 'portfolio'
                                                    ? 'https://a16z.com'
                                                    : 'https://stripe.com'
                                            }
                                            value={url}
                                            onChange={(e) => setUrl(e.target.value)}
                                            required
                                        />
                                    </div>
                                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                                        {mode === 'portfolio'
                                            ? "We'll automatically discover portfolio companies from this URL"
                                            : "We'll analyze this company's website and public data"}
                                    </span>
                                </div>

                                {error && (
                                    <div
                                        style={{
                                            padding: '0.75rem 1rem',
                                            background: 'var(--risk-critical-bg)',
                                            border: '1px solid rgba(239,68,68,0.3)',
                                            borderRadius: 'var(--radius-md)',
                                            color: 'var(--risk-critical)',
                                            fontSize: '0.875rem',
                                        }}
                                    >
                                        {error}
                                    </div>
                                )}

                                <button
                                    type="submit"
                                    className="btn btn-primary btn-lg"
                                    style={{ alignSelf: 'flex-start' }}
                                >
                                    <svg
                                        width="17"
                                        height="17"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                    >
                                        <circle cx="11" cy="11" r="8" />
                                        <path d="m21 21-4.35-4.35" />
                                    </svg>
                                    {mode === 'portfolio'
                                        ? 'Discover Portfolio & Analyze'
                                        : 'Analyze Company'}
                                </button>
                            </form>
                        </div>
                    )}

                    {/* Analyzing / Running Phase */}
                    {(phase === 'analyzing' || phase === 'running') && (
                        <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
                            <div
                                style={{
                                    width: '72px',
                                    height: '72px',
                                    margin: '0 auto 1.5rem',
                                    borderRadius: '50%',
                                    background:
                                        'conic-gradient(var(--accent-blue) 0%, var(--accent-cyan) 50%, var(--bg-surface-3) 50%)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    animation: 'spin 2s linear infinite',
                                }}
                            >
                                <div
                                    style={{
                                        width: '52px',
                                        height: '52px',
                                        borderRadius: '50%',
                                        background: 'var(--bg-surface)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                    }}
                                >
                                    <svg
                                        width="22"
                                        height="22"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="var(--accent-blue)"
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                    >
                                        <circle cx="12" cy="12" r="5" />
                                        <path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12" />
                                    </svg>
                                </div>
                            </div>
                            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                                {phase === 'analyzing' ? 'Analyzing...' : 'Running Portfolio Analysis...'}
                            </h2>
                            <p
                                style={{
                                    color: 'var(--text-secondary)',
                                    marginBottom: '2rem',
                                    fontSize: '0.9375rem',
                                }}
                            >
                                {progressLabel}
                            </p>
                            <div className="progress-bar" style={{ maxWidth: '360px', margin: '0 auto' }}>
                                <div className="progress-fill" style={{ width: `${progress}%` }} />
                            </div>
                            <div
                                style={{
                                    marginTop: '0.75rem',
                                    fontSize: '0.8125rem',
                                    color: 'var(--text-tertiary)',
                                }}
                            >
                                {progress}% complete
                            </div>
                            <p
                                style={{
                                    marginTop: '1.5rem',
                                    fontSize: '0.8125rem',
                                    color: 'var(--text-tertiary)',
                                }}
                            >
                                This typically takes 2–5 minutes. Please keep this page open.
                            </p>
                        </div>
                    )}

                    {/* Portfolio Confirmation Phase */}
                    {phase === 'portfolio_confirm' && (
                        <div>
                            <div
                                className="card"
                                style={{
                                    padding: '1.25rem 1.5rem',
                                    marginBottom: '1.25rem',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '1rem',
                                }}
                            >
                                <div
                                    style={{
                                        width: '40px',
                                        height: '40px',
                                        borderRadius: 'var(--radius-md)',
                                        background: 'var(--risk-low-bg)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        flexShrink: 0,
                                    }}
                                >
                                    <svg
                                        width="20"
                                        height="20"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="var(--risk-low)"
                                        strokeWidth="2"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                    >
                                        <polyline points="20 6 9 17 4 12" />
                                    </svg>
                                </div>
                                <div>
                                    <div style={{ fontWeight: 600 }}>Portfolio companies discovered</div>
                                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                                        Found {companies.length} companies. Review and deselect any you
                                        don&apos;t want to analyze.
                                    </div>
                                </div>
                            </div>

                            <div
                                style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '0.5rem',
                                    marginBottom: '1.5rem',
                                    maxHeight: '400px',
                                    overflowY: 'auto',
                                }}
                            >
                                {companies.map((company, i) => (
                                    <div
                                        key={i}
                                        className="card-surface-2"
                                        style={{
                                            padding: '0.875rem 1rem',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '0.875rem',
                                        }}
                                    >
                                        <input
                                            type="checkbox"
                                            id={`company-${i}`}
                                            checked={company.selected}
                                            onChange={(e) =>
                                                setCompanies((prev) =>
                                                    prev.map((c, idx) =>
                                                        idx === i ? { ...c, selected: e.target.checked } : c
                                                    )
                                                )
                                            }
                                            style={{
                                                width: '16px',
                                                height: '16px',
                                                accentColor: 'var(--accent-blue)',
                                                cursor: 'pointer',
                                            }}
                                        />
                                        <label
                                            htmlFor={`company-${i}`}
                                            style={{ flex: 1, cursor: 'pointer' }}
                                        >
                                            <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>
                                                {company.name}
                                            </div>
                                            <div
                                                style={{
                                                    color: 'var(--text-tertiary)',
                                                    fontSize: '0.8125rem',
                                                }}
                                            >
                                                {company.url}
                                            </div>
                                        </label>
                                    </div>
                                ))}
                            </div>

                            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                                <button onClick={confirmPortfolio} className="btn btn-primary">
                                    Analyze {companies.filter((c) => c.selected).length} Companies
                                </button>
                                <button onClick={() => setPhase('input')} className="btn btn-ghost">
                                    Start Over
                                </button>
                                <span
                                    style={{
                                        color: 'var(--text-tertiary)',
                                        fontSize: '0.8125rem',
                                        marginLeft: 'auto',
                                    }}
                                >
                                    {companies.filter((c) => c.selected).length}/{companies.length} selected
                                </span>
                            </div>
                        </div>
                    )}
                </div>
            </main>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    )
}

export default function NewScanPage() {
    return (
        <SessionWrapper>
            <Suspense
                fallback={
                    <div
                        style={{
                            display: 'flex',
                            minHeight: '100vh',
                            alignItems: 'center',
                            justifyContent: 'center',
                        }}
                    >
                        <div
                            style={{
                                width: '32px',
                                height: '32px',
                                border: '3px solid var(--border)',
                                borderTopColor: 'var(--accent-blue)',
                                borderRadius: '50%',
                                animation: 'spin 1s linear infinite',
                            }}
                        />
                    </div>
                }
            >
                <NewScanContent />
            </Suspense>
        </SessionWrapper>
    )
}
