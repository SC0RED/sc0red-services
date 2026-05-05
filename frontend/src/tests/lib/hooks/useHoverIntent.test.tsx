import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useHoverIntent } from '@/lib/hooks/useHoverIntent'

describe('useHoverIntent', () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })
    afterEach(() => {
        vi.useRealTimers()
    })

    it('starts not-hovered', () => {
        const { result } = renderHook(() => useHoverIntent())
        expect(result.current.hovered).toBe(false)
    })

    it('openNow flips hovered to true synchronously', () => {
        const { result } = renderHook(() => useHoverIntent())
        act(() => {
            result.current.openNow()
        })
        expect(result.current.hovered).toBe(true)
    })

    it('scheduleClose keeps hovered true during the grace period and clears after', () => {
        const { result } = renderHook(() => useHoverIntent(200))
        act(() => {
            result.current.openNow()
        })
        act(() => {
            result.current.scheduleClose()
        })
        // Grace period: still hovered.
        expect(result.current.hovered).toBe(true)
        act(() => {
            vi.advanceTimersByTime(199)
        })
        expect(result.current.hovered).toBe(true)
        // Past the grace period: closed.
        act(() => {
            vi.advanceTimersByTime(2)
        })
        expect(result.current.hovered).toBe(false)
    })

    it('openNow during the grace period cancels the close (safe-transit case)', () => {
        const { result } = renderHook(() => useHoverIntent(200))
        act(() => {
            result.current.openNow()
        })
        act(() => {
            result.current.scheduleClose()
        })
        act(() => {
            // Cursor reached the tooltip / returned to chip — cancel close.
            result.current.openNow()
        })
        // Even after the grace period elapses the tooltip stays open.
        act(() => {
            vi.advanceTimersByTime(500)
        })
        expect(result.current.hovered).toBe(true)
    })

    it('respects a custom close delay', () => {
        const { result } = renderHook(() => useHoverIntent(50))
        act(() => {
            result.current.openNow()
        })
        act(() => {
            result.current.scheduleClose()
        })
        act(() => {
            vi.advanceTimersByTime(60)
        })
        expect(result.current.hovered).toBe(false)
    })

    it('clears any pending close timer on unmount (no setState on unmounted)', () => {
        const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
        const { result, unmount } = renderHook(() => useHoverIntent(200))
        act(() => {
            result.current.openNow()
        })
        act(() => {
            result.current.scheduleClose()
        })
        unmount()
        // If the unmount cleanup didn't cancel the timer, this would
        // attempt setState on the unmounted component and React would
        // log a warning. Pass the warning through `console.error` spy
        // to assert silence.
        act(() => {
            vi.advanceTimersByTime(500)
        })
        expect(consoleErrorSpy).not.toHaveBeenCalled()
        consoleErrorSpy.mockRestore()
    })

    it('exposes setHovered for imperative override (keyboard activation)', () => {
        const { result } = renderHook(() => useHoverIntent())
        act(() => {
            result.current.setHovered(true)
        })
        expect(result.current.hovered).toBe(true)
        act(() => {
            result.current.setHovered((current) => !current)
        })
        expect(result.current.hovered).toBe(false)
    })
})
