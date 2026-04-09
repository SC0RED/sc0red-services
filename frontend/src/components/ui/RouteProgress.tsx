'use client'

import { useEffect, useState } from 'react'
import { usePathname } from 'next/navigation'

export default function RouteProgress() {
    const pathname = usePathname()
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        setLoading(true)
        const timeout = setTimeout(() => setLoading(false), 500)
        return () => clearTimeout(timeout)
    }, [pathname])

    if (!loading) return null

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                height: '3px',
                zIndex: 9999,
                background: 'var(--bg-surface-2)',
            }}
        >
            <div
                style={{
                    height: '100%',
                    background: 'linear-gradient(90deg, var(--accent-blue), var(--accent-cyan))',
                    animation: 'route-progress 500ms ease-out forwards',
                }}
            />
        </div>
    )
}
