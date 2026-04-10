type SkeletonVariant = 'text' | 'card' | 'table-row' | 'stat-card' | 'circle'

interface SkeletonProps {
    variant?: SkeletonVariant
    width?: string
    height?: string
    count?: number
}

const VARIANT_STYLES: Record<SkeletonVariant, React.CSSProperties> = {
    text: { height: '1rem', borderRadius: '4px' },
    card: { height: '120px', borderRadius: 'var(--radius-md)' },
    'table-row': { height: '3rem', borderRadius: '4px' },
    'stat-card': { height: '80px', borderRadius: 'var(--radius-md)' },
    circle: { width: '40px', height: '40px', borderRadius: '50%' },
}

export default function Skeleton({ variant = 'text', width, height, count = 1 }: SkeletonProps) {
    const baseStyle = VARIANT_STYLES[variant]

    return (
        <>
            {Array.from({ length: count }, (_, index) => (
                <div
                    key={index}
                    className="skeleton"
                    style={{
                        ...baseStyle,
                        ...(width ? { width } : {}),
                        ...(height ? { height } : {}),
                        marginBottom: count > 1 ? '0.5rem' : undefined,
                    }}
                />
            ))}
        </>
    )
}
