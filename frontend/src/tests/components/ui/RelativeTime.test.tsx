import { render, screen, act } from '@testing-library/react'
import { renderToString } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import RelativeTime from '@/components/ui/RelativeTime'

/**
 * Tests for the SSR-safe relative-time component.
 *
 * Strategy: with a fixed `Date.now()` (vi.setSystemTime) we can assert both
 * the deterministic SSR-shape label AND the post-mount relative label.
 *
 * The component seeds `useState` with the absolute (UTC-formatted) date
 * before the effect runs, then the effect overwrites it with the relative
 * phrase. React 18's `act()` flushes effects, so after the initial render
 * the relative phrase is what's in the DOM. To assert the SSR / pre-effect
 * shape, we render with effects suppressed and inspect the DOM before the
 * scheduler ticks.
 */

const FIXED_NOW = new Date('2026-04-27T12:00:00Z')

describe('RelativeTime', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        vi.setSystemTime(FIXED_NOW)
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    it('renders fallback when value is undefined', () => {
        render(<RelativeTime value={undefined} />)
        expect(screen.getByText('—')).toBeInTheDocument()
        expect(screen.queryByRole('time')).not.toBeInTheDocument()
    })

    it('renders fallback when value is null', () => {
        render(<RelativeTime value={null} />)
        expect(screen.getByText('—')).toBeInTheDocument()
    })

    it('renders fallback when value is invalid', () => {
        render(<RelativeTime value="not a date" />)
        expect(screen.getByText('—')).toBeInTheDocument()
    })

    it('respects custom fallback prop', () => {
        render(<RelativeTime value={undefined} fallback="Never" />)
        expect(screen.getByText('Never')).toBeInTheDocument()
    })

    it('emits deterministic absolute UTC date in SSR HTML', () => {
        // SSR runs `useState` once but never the effect. The rendered HTML
        // is what the browser hydrates into; if it doesn't match the
        // client's first paint, React logs a hydration warning.
        const html = renderToString(<RelativeTime value="2026-04-20T08:30:00Z" />)
        expect(html).toContain('Apr 20, 2026')
        // React serialises the JSX `dateTime` prop as the lowercase HTML
        // attribute `datetime`. Case-insensitive regex flag is defensive —
        // not strictly needed today but harmless.
        expect(html).toMatch(/datetime="2026-04-20T08:30:00\.000Z"/i)
    })

    it('SSR output is timezone-independent (formats in UTC)', () => {
        // `new Date('2026-04-20T00:30:00Z')` is "Apr 20" in UTC but would be
        // "Apr 19" when formatted in PT (UTC-7/8). The component must use
        // UTC for SSR to keep server and client HTML identical.
        const html = renderToString(<RelativeTime value="2026-04-20T00:30:00Z" />)
        expect(html).toContain('Apr 20, 2026')
        expect(html).not.toContain('Apr 19')
    })

    it('swaps to "just now" for sub-30-second age after mount', () => {
        // 10 seconds ago.
        render(<RelativeTime value="2026-04-27T11:59:50Z" />)
        const time = screen.getByText('just now')
        expect(time.tagName).toBe('TIME')
    })

    it('swaps to relative phrase after mount for older timestamps', () => {
        // 3 hours ago.
        render(<RelativeTime value="2026-04-27T09:00:00Z" />)
        const time = screen.getByText(/3 hours ago/)
        expect(time.tagName).toBe('TIME')
    })

    it('uses "in N" prefix for future timestamps (clock skew tolerance)', () => {
        // 5 minutes in the future.
        render(<RelativeTime value="2026-04-27T12:05:00Z" />)
        // date-fns produces "in about X minutes" / "in 5 minutes" depending
        // on bucket; we just assert the future prefix.
        expect(screen.getByText(/in /)).toBeInTheDocument()
    })

    it('exposes ISO timestamp via dateTime attribute', () => {
        render(<RelativeTime value="2026-04-27T09:00:00Z" />)
        const time = screen.getByText(/3 hours ago/)
        expect(time.getAttribute('dateTime')).toBe('2026-04-27T09:00:00.000Z')
    })

    it('exposes full local-time absolute via title attribute for hover tooltip', () => {
        render(<RelativeTime value="2026-04-27T09:00:00Z" />)
        const time = screen.getByText(/3 hours ago/)
        const title = time.getAttribute('title')
        expect(title).toBeTruthy()
        // Title is a full date-fns 'PPpp' format, e.g. "Apr 27, 2026 at 9:00:00 AM".
        // We avoid asserting exact local formatting (timezone-dependent) and
        // assert the year is present so we know it's a real human-readable
        // absolute, not "just now" or another relative phrase.
        expect(title).toContain('2026')
    })

    it('re-ticks the relative label after a minute elapses', () => {
        // Start at "1 minute ago" (60s old).
        render(<RelativeTime value="2026-04-27T11:59:00Z" />)
        expect(screen.getByText(/1 minute ago/)).toBeInTheDocument()

        // Advance fake time + the interval the component schedules.
        act(() => {
            vi.advanceTimersByTime(60_000)
        })

        // Now 2 minutes old.
        expect(screen.getByText(/2 minutes ago/)).toBeInTheDocument()
    })

    it('updates label when the value prop changes to a new timestamp', () => {
        const { rerender } = render(<RelativeTime value="2026-04-27T11:59:00Z" />)
        expect(screen.getByText(/1 minute ago/)).toBeInTheDocument()

        rerender(<RelativeTime value="2026-04-27T09:00:00Z" />)
        expect(screen.getByText(/3 hours ago/)).toBeInTheDocument()
    })

    it('clears the re-tick interval on unmount', () => {
        // Regression guard against the cleanup line being removed: if the
        // effect's `return () => clearInterval(...)` ever disappears, this
        // test fails. Especially important for the activity-feed pattern
        // (Tier 2 §5) which mounts/unmounts RelativeTime instances on
        // every poll cycle.
        const clearSpy = vi.spyOn(globalThis, 'clearInterval')
        const before = clearSpy.mock.calls.length

        const { unmount } = render(<RelativeTime value="2026-04-27T09:00:00Z" />)
        unmount()

        expect(clearSpy.mock.calls.length).toBeGreaterThan(before)
        clearSpy.mockRestore()
    })
})
