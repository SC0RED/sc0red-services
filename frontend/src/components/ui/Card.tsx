import { type HTMLAttributes, type ReactNode } from 'react'

type CardPadding = 'sm' | 'md' | 'lg' | 'none'

const PADDING_MAP: Record<CardPadding, string> = {
    none: '0',
    sm: '1rem',
    md: '1.5rem',
    lg: '2rem',
}

interface CardProps extends HTMLAttributes<HTMLDivElement> {
    padding?: CardPadding
    header?: ReactNode
}

export default function Card({
    padding = 'md',
    header,
    children,
    className = '',
    style,
    ...props
}: CardProps) {
    return (
        <div
            className={`card ${className}`.trim()}
            style={{ padding: PADDING_MAP[padding], ...style }}
            {...props}
        >
            {header && (
                <div
                    style={{
                        marginBottom: '1rem',
                        paddingBottom: '1rem',
                        borderBottom: '1px solid var(--border-subtle)',
                    }}
                >
                    {header}
                </div>
            )}
            {children}
        </div>
    )
}
