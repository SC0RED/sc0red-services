import { type HTMLAttributes } from 'react'

type BadgeVariant = 'low' | 'moderate' | 'high' | 'critical' | 'blue' | 'cyan' | 'neutral'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
    variant?: BadgeVariant
}

export default function Badge({ variant = 'neutral', children, className = '', ...props }: BadgeProps) {
    return (
        <span className={`badge badge-${variant} ${className}`.trim()} {...props}>
            {children}
        </span>
    )
}
