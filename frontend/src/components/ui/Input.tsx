import { type InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
    error?: string
}

export default function Input({ error, className = '', ...props }: InputProps) {
    const classes = `input ${error ? 'input-error' : ''} ${className}`.trim()

    return (
        <div>
            <input className={classes} aria-invalid={!!error} {...props} />
            {error && (
                <p className="input-error-message" role="alert">
                    {error}
                </p>
            )}
        </div>
    )
}
