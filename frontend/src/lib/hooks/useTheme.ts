'use client'

import { useCallback, useEffect, useState } from 'react'

/**
 * Theme system for the Janus webapp.
 *
 * Three user-facing modes are persisted under `localStorage.janus.theme`:
 *   - `"dark"`   — explicit dark
 *   - `"light"`  — explicit light
 *   - `"system"` — follow `prefers-color-scheme` on every page load
 *
 * The actual `<html data-theme>` attribute is always one of `"dark"` or
 * `"light"` (system is resolved at write time). The synchronous bootstrap
 * script in `app/layout.tsx` sets the attribute before React hydrates, so
 * the user never sees a flash-of-wrong-theme.
 *
 * Charts and other JS consumers subscribe to the `janus:theme-change` custom
 * event dispatched by `setTheme`; that's how Recharts re-resolves CSS
 * variables when the user toggles the theme.
 */

export type ThemeMode = 'dark' | 'light' | 'system'
export type ResolvedTheme = 'dark' | 'light'

export const THEME_STORAGE_KEY = 'janus.theme'
export const THEME_CHANGE_EVENT = 'janus:theme-change'

interface ThemeChangeDetail {
    mode: ThemeMode
    resolved: ResolvedTheme
}

function readStoredMode(): ThemeMode {
    // Default for new users (or anyone with cleared / unreadable storage)
    // is `'dark'`, NOT `'system'` — sc0red is dark-first by design and a
    // light-OS laptop user shouldn't see a light webapp on first paint.
    // The Settings → Appearance radio reflects this: "Dark" is highlighted
    // until the user picks something. Must stay in lockstep with the
    // bootstrap script in `app/layout.tsx`. See
    // `openspec/changes/dark-default-theme/proposal.md`.
    if (typeof window === 'undefined') return 'dark'
    try {
        const raw = window.localStorage.getItem(THEME_STORAGE_KEY)
        if (raw === 'dark' || raw === 'light' || raw === 'system') return raw
    } catch {
        // Safari private mode throws on localStorage access — fall through.
    }
    return 'dark'
}

function readSystemTheme(): ResolvedTheme {
    if (typeof window === 'undefined' || !window.matchMedia) return 'dark'
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function readDocumentTheme(): ResolvedTheme {
    if (typeof document === 'undefined') return 'dark'
    const attribute = document.documentElement.getAttribute('data-theme')
    return attribute === 'light' ? 'light' : 'dark'
}

export function resolveMode(mode: ThemeMode): ResolvedTheme {
    return mode === 'system' ? readSystemTheme() : mode
}

/**
 * Applies a theme choice: writes localStorage, updates `<html data-theme>`,
 * and dispatches `janus:theme-change` so JS subscribers (charts) can
 * re-resolve their CSS variables. Safe to call on the server (no-op).
 */
export function setTheme(mode: ThemeMode): ResolvedTheme {
    if (typeof document === 'undefined') return 'dark'
    const resolved = resolveMode(mode)
    try {
        window.localStorage.setItem(THEME_STORAGE_KEY, mode)
    } catch {
        // Persistence failed (private mode); the in-memory change still applies.
    }
    document.documentElement.setAttribute('data-theme', resolved)
    window.dispatchEvent(
        new CustomEvent<ThemeChangeDetail>(THEME_CHANGE_EVENT, {
            detail: { mode, resolved },
        })
    )
    return resolved
}

interface UseThemeReturn {
    /** The user's stored preference (dark / light / system). */
    mode: ThemeMode
    /** The currently-applied theme on `<html>`. Always concrete. */
    resolved: ResolvedTheme
    /** Updates the preference, writes localStorage, and re-applies. */
    setTheme: (mode: ThemeMode) => void
}

export function useTheme(): UseThemeReturn {
    const [mode, setMode] = useState<ThemeMode>(() => readStoredMode())
    const [resolved, setResolved] = useState<ResolvedTheme>(() => readDocumentTheme())

    useEffect(() => {
        const handleChange = (event: Event) => {
            // The event contract requires `detail`; a missing detail is a
            // wiring bug at the dispatch site and should crash visibly here
            // rather than silently no-op.
            const { mode: nextMode, resolved: nextResolved } = (event as CustomEvent<ThemeChangeDetail>)
                .detail
            setMode(nextMode)
            setResolved(nextResolved)
        }
        window.addEventListener(THEME_CHANGE_EVENT, handleChange)
        return () => window.removeEventListener(THEME_CHANGE_EVENT, handleChange)
    }, [])

    // When the user is in system mode, follow OS-level theme changes live.
    useEffect(() => {
        if (mode !== 'system' || typeof window === 'undefined' || !window.matchMedia) return
        const media = window.matchMedia('(prefers-color-scheme: light)')
        const handleSystemChange = () => {
            const next: ResolvedTheme = media.matches ? 'light' : 'dark'
            document.documentElement.setAttribute('data-theme', next)
            setResolved(next)
            window.dispatchEvent(
                new CustomEvent<ThemeChangeDetail>(THEME_CHANGE_EVENT, {
                    detail: { mode: 'system', resolved: next },
                })
            )
        }
        media.addEventListener('change', handleSystemChange)
        return () => media.removeEventListener('change', handleSystemChange)
    }, [mode])

    const update = useCallback((next: ThemeMode) => {
        const nextResolved = setTheme(next)
        setMode(next)
        setResolved(nextResolved)
    }, [])

    return { mode, resolved, setTheme: update }
}
