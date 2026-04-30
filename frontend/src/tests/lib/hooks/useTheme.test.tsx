import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import { THEME_CHANGE_EVENT, THEME_STORAGE_KEY, resolveMode, setTheme, useTheme } from '@/lib/hooks/useTheme'

interface MediaQueryListMock {
    matches: boolean
    addEventListener: (type: string, listener: (event: MediaQueryListEvent) => void) => void
    removeEventListener: (type: string, listener: (event: MediaQueryListEvent) => void) => void
    dispatchEvent: (event: MediaQueryListEvent) => boolean
    fireChange: (matches: boolean) => void
}

function installMatchMedia(initialMatches: boolean): MediaQueryListMock {
    const listeners = new Set<(event: MediaQueryListEvent) => void>()
    const mql: MediaQueryListMock = {
        matches: initialMatches,
        addEventListener: (_type, listener) => {
            listeners.add(listener)
        },
        removeEventListener: (_type, listener) => {
            listeners.delete(listener)
        },
        dispatchEvent: () => true,
        fireChange: (matches: boolean) => {
            mql.matches = matches
            const event = { matches } as MediaQueryListEvent
            listeners.forEach((listener) => listener(event))
        },
    }
    window.matchMedia = vi.fn(() => mql) as unknown as typeof window.matchMedia
    return mql
}

beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    installMatchMedia(false)
})

describe('resolveMode', () => {
    it('returns the explicit mode when not "system"', () => {
        expect(resolveMode('dark')).toBe('dark')
        expect(resolveMode('light')).toBe('light')
    })

    it('resolves "system" against prefers-color-scheme: light', () => {
        installMatchMedia(true)
        expect(resolveMode('system')).toBe('light')
    })

    it('resolves "system" to dark when OS reports dark', () => {
        installMatchMedia(false)
        expect(resolveMode('system')).toBe('dark')
    })
})

describe('setTheme', () => {
    it('persists the mode to localStorage', () => {
        setTheme('light')
        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
    })

    it('writes data-theme on <html>', () => {
        setTheme('light')
        expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    })

    it('dispatches the janus:theme-change custom event', () => {
        const listener = vi.fn()
        window.addEventListener(THEME_CHANGE_EVENT, listener)
        setTheme('light')
        expect(listener).toHaveBeenCalledTimes(1)
        const event = listener.mock.calls[0][0] as CustomEvent<{
            mode: string
            resolved: string
        }>
        expect(event.detail.mode).toBe('light')
        expect(event.detail.resolved).toBe('light')
        window.removeEventListener(THEME_CHANGE_EVENT, listener)
    })

    it('resolves system mode at write time', () => {
        installMatchMedia(true)
        setTheme('system')
        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('system')
        expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    })
})

describe('useTheme', () => {
    it('reads the persisted mode on first render', () => {
        window.localStorage.setItem(THEME_STORAGE_KEY, 'light')
        document.documentElement.setAttribute('data-theme', 'light')
        const { result } = renderHook(() => useTheme())
        expect(result.current.mode).toBe('light')
        expect(result.current.resolved).toBe('light')
    })

    it('defaults to system when nothing persisted', () => {
        const { result } = renderHook(() => useTheme())
        expect(result.current.mode).toBe('system')
    })

    it('updates on setTheme()', () => {
        const { result } = renderHook(() => useTheme())
        act(() => result.current.setTheme('light'))
        expect(result.current.mode).toBe('light')
        expect(result.current.resolved).toBe('light')
        expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    })

    it('reflects external theme-change events (e.g. from another component)', () => {
        const { result } = renderHook(() => useTheme())
        act(() => {
            window.dispatchEvent(
                new CustomEvent(THEME_CHANGE_EVENT, {
                    detail: { mode: 'dark', resolved: 'dark' },
                })
            )
        })
        expect(result.current.mode).toBe('dark')
        expect(result.current.resolved).toBe('dark')
    })

    it('follows OS-level changes when in system mode', () => {
        const mql = installMatchMedia(false)
        const { result } = renderHook(() => useTheme())
        // Default mode is "system".
        expect(result.current.mode).toBe('system')

        act(() => {
            mql.fireChange(true)
        })
        expect(result.current.resolved).toBe('light')
        expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    })

    it('ignores OS-level changes when in explicit mode', () => {
        const mql = installMatchMedia(false)
        const { result } = renderHook(() => useTheme())
        act(() => result.current.setTheme('dark'))

        act(() => {
            mql.fireChange(true)
        })
        // Explicit dark — should NOT flip to light just because OS did.
        expect(result.current.resolved).toBe('dark')
    })
})
