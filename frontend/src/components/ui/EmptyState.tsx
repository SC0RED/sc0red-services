import { type ReactNode } from 'react'

interface EmptyStateProps {
    icon?: ReactNode
    title: string
    description?: string
    action?: ReactNode
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
    return (
        <div className="card" style={{ padding: '3rem', textAlign: 'center' }}>
            {icon && <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>{icon}</div>}
            <h2 style={{ fontWeight: 700, marginBottom: '0.75rem' }}>{title}</h2>
            {description && (
                <p
                    style={{
                        color: 'var(--text-secondary)',
                        marginBottom: action ? '2rem' : '0',
                        maxWidth: '400px',
                        margin: action ? '0 auto 2rem' : '0 auto',
                    }}
                >
                    {description}
                </p>
            )}
            {action && <div>{action}</div>}
        </div>
    )
}
