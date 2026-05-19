import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'

import { THEME_CHANGE_EVENT } from '@/lib/hooks/useTheme'
import { useThemedColor, useThemedColors } from '@/lib/utils/themedColor'

beforeEach(() => {
    document.documentElement.style.removeProperty('--risk-low')
    document.documentElement.style.removeProperty('--risk-critical')
})

describe('useThemedColor', () => {
    it('returns the resolved CSS variable value after mount', () => {
        document.documentElement.style.setProperty('--risk-low', '#22c55e')
        const { result } = renderHook(() => useThemedColor('--risk-low', '#000'))
        expect(result.current).toBe('#22c55e')
    })

    it('returns the fallback before mount / when token undefined', () => {
        const { result } = renderHook(() => useThemedColor('--nonexistent-token', '#fallback'))
        expect(result.current).toBe('#fallback')
    })

    it('re-resolves when sc0red-services:theme-change fires', () => {
        document.documentElement.style.setProperty('--risk-low', '#22c55e')
        const { result } = renderHook(() => useThemedColor('--risk-low', '#000'))
        expect(result.current).toBe('#22c55e')

        act(() => {
            document.documentElement.style.setProperty('--risk-low', '#16a34a')
            window.dispatchEvent(
                new CustomEvent(THEME_CHANGE_EVENT, {
                    detail: { mode: 'light', resolved: 'light' },
                })
            )
        })
        expect(result.current).toBe('#16a34a')
    })

    it('cleans up its event listener on unmount', () => {
        const removeSpy = vi.spyOn(window, 'removeEventListener')
        const { unmount } = renderHook(() => useThemedColor('--risk-low', '#000'))
        unmount()
        expect(removeSpy).toHaveBeenCalledWith(THEME_CHANGE_EVENT, expect.any(Function))
        removeSpy.mockRestore()
    })
})

describe('useThemedColors', () => {
    it('returns a map of resolved values for the requested tokens', () => {
        document.documentElement.style.setProperty('--risk-low', '#22c55e')
        document.documentElement.style.setProperty('--risk-critical', '#ef4444')
        const tokens = ['--risk-low', '--risk-critical'] as const
        const { result } = renderHook(() => useThemedColors(tokens))
        expect(result.current['--risk-low']).toBe('#22c55e')
        expect(result.current['--risk-critical']).toBe('#ef4444')
    })

    it('updates all entries on theme change', () => {
        document.documentElement.style.setProperty('--risk-low', '#22c55e')
        const tokens = ['--risk-low'] as const
        const { result } = renderHook(() => useThemedColors(tokens))
        expect(result.current['--risk-low']).toBe('#22c55e')

        act(() => {
            document.documentElement.style.setProperty('--risk-low', '#16a34a')
            window.dispatchEvent(
                new CustomEvent(THEME_CHANGE_EVENT, {
                    detail: { mode: 'light', resolved: 'light' },
                })
            )
        })
        expect(result.current['--risk-low']).toBe('#16a34a')
    })
})
