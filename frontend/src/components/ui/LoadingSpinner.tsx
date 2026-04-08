type SpinnerSize = 'sm' | 'md' | 'lg'

const SIZE_MAP: Record<SpinnerSize, number> = {
    sm: 16,
    md: 24,
    lg: 40,
}

interface LoadingSpinnerProps {
    size?: SpinnerSize
}

export default function LoadingSpinner({ size = 'md' }: LoadingSpinnerProps) {
    const pixels = SIZE_MAP[size]

    return (
        <svg
            style={{ animation: 'spin 1s linear infinite' }}
            width={pixels}
            height={pixels}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-label="Loading"
            role="status"
        >
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
        </svg>
    )
}
