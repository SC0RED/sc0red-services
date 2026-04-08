import type { Phase } from '@/lib/types/scan'

interface ScanProgressPhaseProps {
    phase: Extract<Phase, 'analyzing' | 'running'>
    progress: number
    progressLabel: string
}

export default function ScanProgressPhase({ phase, progress, progressLabel }: ScanProgressPhaseProps) {
    return (
        <div
            className="card"
            style={{ padding: '3rem', textAlign: 'center' }}
            aria-live="polite"
            role="status"
        >
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
                <div className="progress-fill" style={{ width: `${Math.round(progress)}%` }} />
            </div>
            <div
                style={{
                    marginTop: '0.75rem',
                    fontSize: '0.8125rem',
                    color: 'var(--text-tertiary)',
                }}
            >
                {Math.round(progress)}% complete
            </div>
            <p
                style={{
                    marginTop: '1.5rem',
                    fontSize: '0.8125rem',
                    color: 'var(--text-tertiary)',
                }}
            >
                This typically takes 1–3 minutes. Please keep this page open.
            </p>
        </div>
    )
}
