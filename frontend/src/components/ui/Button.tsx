import { type ButtonHTMLAttributes, type ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: ButtonVariant
    size?: ButtonSize
    loading?: boolean
    icon?: ReactNode
}

export default function Button({
    variant = 'primary',
    size = 'md',
    loading = false,
    icon,
    children,
    className = '',
    disabled,
    ...props
}: ButtonProps) {
    const classes = `btn btn-${variant} btn-${size} ${className}`.trim()

    return (
        <button className={classes} disabled={disabled || loading} {...props}>
            {loading ? (
                <>
                    <svg
                        style={{ animation: 'spin 1s linear infinite' }}
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                    >
                        <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                    {children}
                </>
            ) : (
                <>
                    {icon}
                    {children}
                </>
            )}
        </button>
    )
}
