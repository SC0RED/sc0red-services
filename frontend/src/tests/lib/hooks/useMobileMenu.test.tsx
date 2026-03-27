import { renderHook, act } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

vi.mock('next/navigation', () => ({
    usePathname: () => '/dashboard',
}))

import { useMobileMenu } from '@/lib/hooks/useMobileMenu'

describe('useMobileMenu', () => {
    beforeEach(() => {
        document.body.style.overflow = ''
    })

    it('starts closed', () => {
        const { result } = renderHook(() => useMobileMenu())
        expect(result.current.isOpen).toBe(false)
    })

    it('opens on open()', () => {
        const { result } = renderHook(() => useMobileMenu())
        act(() => result.current.open())
        expect(result.current.isOpen).toBe(true)
    })

    it('closes on close()', () => {
        const { result } = renderHook(() => useMobileMenu())
        act(() => result.current.open())
        act(() => result.current.close())
        expect(result.current.isOpen).toBe(false)
    })

    it('locks body scroll when open', () => {
        const { result } = renderHook(() => useMobileMenu())
        act(() => result.current.open())
        expect(document.body.style.overflow).toBe('hidden')
    })

    it('unlocks body scroll when closed', () => {
        const { result } = renderHook(() => useMobileMenu())
        act(() => result.current.open())
        act(() => result.current.close())
        expect(document.body.style.overflow).toBe('')
    })

    it('closes on Escape key', () => {
        const { result } = renderHook(() => useMobileMenu())
        act(() => result.current.open())
        expect(result.current.isOpen).toBe(true)

        act(() => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
        })
        expect(result.current.isOpen).toBe(false)
    })

    it('does not respond to Escape when closed', () => {
        const { result } = renderHook(() => useMobileMenu())
        act(() => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
        })
        expect(result.current.isOpen).toBe(false)
    })

    it('provides refs for hamburger and close buttons', () => {
        const { result } = renderHook(() => useMobileMenu())
        expect(result.current.hamburgerRef).toBeDefined()
        expect(result.current.closeRef).toBeDefined()
    })
})
