import type { Mode } from '@/lib/types/scan'

interface ScanInputPhaseProps {
    mode: Mode
    url: string
    error: string
    onModeChange: (mode: Mode) => void
    onUrlChange: (url: string) => void
    onSubmit: (e: React.FormEvent) => void
}

const MODE_OPTIONS: { value: Mode; label: string; desc: string; icon: React.ReactNode }[] = [
    {
        value: 'portfolio',
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
        value: 'standalone',
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
]

export default function ScanInputPhase({
    mode,
    url,
    error,
    onModeChange,
    onUrlChange,
    onSubmit,
}: ScanInputPhaseProps) {
    return (
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
                {MODE_OPTIONS.map((opt) => (
                    <button
                        key={opt.value}
                        type="button"
                        onClick={() => onModeChange(opt.value)}
                        style={{
                            padding: '1.25rem',
                            borderRadius: 'var(--radius-lg)',
                            border:
                                mode === opt.value
                                    ? '2px solid var(--accent-blue)'
                                    : '1px solid var(--border)',
                            background: mode === opt.value ? 'rgba(59,123,246,0.06)' : 'var(--bg-surface)',
                            textAlign: 'left',
                            cursor: 'pointer',
                            transition: 'all var(--transition-fast)',
                        }}
                    >
                        <div
                            style={{
                                color: mode === opt.value ? 'var(--accent-blue)' : 'var(--text-secondary)',
                                marginBottom: '0.625rem',
                            }}
                        >
                            {opt.icon}
                        </div>
                        <div
                            style={{
                                fontWeight: 600,
                                marginBottom: '0.25rem',
                                color: mode === opt.value ? 'var(--text-primary)' : 'var(--text-secondary)',
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

            <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
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
                            placeholder={mode === 'portfolio' ? 'https://a16z.com' : 'https://stripe.com'}
                            value={url}
                            onChange={(e) => onUrlChange(e.target.value)}
                            required
                        />
                    </div>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--text-tertiary)' }}>
                        {mode === 'portfolio'
                            ? "We'll automatically discover portfolio companies from this URL"
                            : "We'll analyze this company's website and public data"}
                    </span>
                </div>

                {error && <div className="alert-error">{error}</div>}

                <button type="submit" className="btn btn-primary btn-lg" style={{ alignSelf: 'flex-start' }}>
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
                    {mode === 'portfolio' ? 'Discover Portfolio & Analyze' : 'Analyze Company'}
                </button>
            </form>
        </div>
    )
}
