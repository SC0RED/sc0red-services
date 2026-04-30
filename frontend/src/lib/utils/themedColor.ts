'use client'

import { useEffect, useState } from 'react'

import { THEME_CHANGE_EVENT } from '@/lib/hooks/useTheme'

/**
 * Resolves a CSS custom property (e.g. `--risk-low`) to its current
 * concrete value. Useful for libraries that read color props
 * programmatically and don't carry CSS-variable references through
 * (Recharts custom shapes, canvas-rendered charts, etc).
 *
 * - On the server / before hydration, returns `fallback`.
 * - On the client, reads `getComputedStyle(html).getPropertyValue(token)`.
 * - Re-resolves on `janus:theme-change`, so charts that consume the value
 *   re-render with the new palette when the user toggles theme.
 */
export function useThemedColor(token: string, fallback = ''): string {
    const [value, setValue] = useState<string>(fallback)

    useEffect(() => {
        const resolve = () => {
            const computed = getComputedStyle(document.documentElement).getPropertyValue(token).trim()
            setValue(computed || fallback)
        }
        resolve()
        window.addEventListener(THEME_CHANGE_EVENT, resolve)
        return () => window.removeEventListener(THEME_CHANGE_EVENT, resolve)
    }, [token, fallback])

    return value
}

/**
 * Batched form of {@link useThemedColor} for components that need many
 * tokens (e.g. a multi-series chart). Returns an object keyed by the
 * input token name with resolved hex strings.
 */
export function useThemedColors(tokens: readonly string[]): Record<string, string> {
    const [values, setValues] = useState<Record<string, string>>(() =>
        Object.fromEntries(tokens.map((t) => [t, '']))
    )

    // `tokens` is an array reference; if a caller passes an inline literal it
    // will be a new reference every render. Stringify it for the dep so we
    // re-subscribe only when the *contents* change, not the array identity.
    const tokenKey = tokens.join(',')
    useEffect(() => {
        const resolve = () => {
            const style = getComputedStyle(document.documentElement)
            const next: Record<string, string> = {}
            tokens.forEach((token) => {
                next[token] = style.getPropertyValue(token).trim()
            })
            setValues(next)
        }
        resolve()
        window.addEventListener(THEME_CHANGE_EVENT, resolve)
        return () => window.removeEventListener(THEME_CHANGE_EVENT, resolve)
        // eslint-disable-next-line react-hooks/exhaustive-deps -- see tokenKey
    }, [tokenKey])

    return values
}
