import Link from 'next/link'

export default function NotFound() {
    return (
        <div
            style={{
                display: 'flex',
                minHeight: '100vh',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '2rem',
            }}
        >
            <div className="card" style={{ padding: '3rem', textAlign: 'center', maxWidth: '480px' }}>
                <div
                    style={{
                        width: '64px',
                        height: '64px',
                        margin: '0 auto 1.5rem',
                        borderRadius: '50%',
                        background: 'rgba(59,123,246,0.1)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}
                >
                    <svg
                        width="28"
                        height="28"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="var(--accent-blue)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                    >
                        <circle cx="11" cy="11" r="8" />
                        <path d="m21 21-4.35-4.35" />
                        <line x1="8" y1="11" x2="14" y2="11" />
                    </svg>
                </div>

                <h1 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                    Page not found
                </h1>
                <p
                    style={{
                        color: 'var(--text-secondary)',
                        fontSize: '0.9375rem',
                        marginBottom: '2rem',
                        lineHeight: 1.6,
                    }}
                >
                    The page you&apos;re looking for doesn&apos;t exist or has been moved.
                </p>

                <Link href="/dashboard" className="btn btn-primary">
                    Go to Dashboard
                </Link>
            </div>
        </div>
    )
}
