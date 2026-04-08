import { type ReactNode } from 'react'

interface FormFieldProps {
    label: string
    htmlFor?: string
    required?: boolean
    error?: string
    helperText?: string
    children: ReactNode
}

export default function FormField({
    label,
    htmlFor,
    required = false,
    error,
    helperText,
    children,
}: FormFieldProps) {
    return (
        <div className="input-group">
            <label className="label" htmlFor={htmlFor}>
                {label}
                {required && <span style={{ color: 'var(--risk-critical)', marginLeft: '0.25rem' }}>*</span>}
            </label>
            {children}
            {error && (
                <p className="input-error-message" role="alert">
                    {error}
                </p>
            )}
            {!error && helperText && (
                <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '0.25rem' }}>
                    {helperText}
                </p>
            )}
        </div>
    )
}
