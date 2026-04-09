import { type SelectHTMLAttributes } from 'react'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
    error?: string
}

export default function Select({ error, className = '', children, ...props }: SelectProps) {
    const classes = `input ${error ? 'input-error' : ''} ${className}`.trim()

    return (
        <div>
            <select className={classes} aria-invalid={!!error} {...props}>
                {children}
            </select>
            {error && (
                <p className="input-error-message" role="alert">
                    {error}
                </p>
            )}
        </div>
    )
}
