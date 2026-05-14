interface TopActionsCalloutProps {
    actions: string[]
}

export default function TopActionsCallout({ actions }: TopActionsCalloutProps) {
    if (actions.length === 0) return null

    return (
        <div
            className="card card--rich"
            style={{
                marginBottom: '1.5rem',
                borderColor: 'rgba(59,123,246,0.3)',
                background: 'rgba(59,123,246,0.04)',
            }}
        >
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.625rem',
                    marginBottom: '0.875rem',
                }}
            >
                <svg
                    width="17"
                    height="17"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="var(--accent-blue)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
                <span
                    style={{
                        fontWeight: 700,
                        color: 'var(--accent-blue)',
                        fontSize: '0.875rem',
                    }}
                >
                    Top 3 Immediate Actions
                </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {actions.map((action, i) => (
                    <div
                        key={i}
                        style={{
                            display: 'flex',
                            gap: '0.75rem',
                            alignItems: 'flex-start',
                        }}
                    >
                        <span
                            style={{
                                minWidth: '22px',
                                height: '22px',
                                borderRadius: '50%',
                                background: 'rgba(59,123,246,0.15)',
                                color: 'var(--accent-blue)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                flexShrink: 0,
                                marginTop: '1px',
                            }}
                        >
                            {i + 1}
                        </span>
                        <p
                            style={{
                                fontSize: '0.875rem',
                                color: 'var(--text-primary)',
                                lineHeight: 1.6,
                            }}
                        >
                            {action}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    )
}
