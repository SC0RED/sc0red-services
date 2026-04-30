import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'

import ThemeToggle from '@/components/ThemeToggle'
import { THEME_STORAGE_KEY } from '@/lib/hooks/useTheme'

beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    // Default to a deterministic OS preference (dark) so "system" → dark.
    Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: () => ({
            matches: false,
            addEventListener: () => {},
            removeEventListener: () => {},
            dispatchEvent: () => true,
        }),
    })
})

describe('ThemeToggle', () => {
    it('renders three options labelled Dark / Light / System', () => {
        render(<ThemeToggle />)
        expect(screen.getByLabelText('Dark', { exact: false })).toBeInTheDocument()
        expect(screen.getByLabelText('Light', { exact: false })).toBeInTheDocument()
        expect(screen.getByLabelText('System', { exact: false })).toBeInTheDocument()
    })

    it('reflects the persisted mode as the checked option', () => {
        window.localStorage.setItem(THEME_STORAGE_KEY, 'light')
        render(<ThemeToggle />)
        const light = screen.getByRole('radio', { name: /Light/i }) as HTMLInputElement
        expect(light.checked).toBe(true)
    })

    it('writes localStorage and <html data-theme> when the user picks Light', () => {
        render(<ThemeToggle />)
        const light = screen.getByRole('radio', { name: /Light/i }) as HTMLInputElement
        fireEvent.click(light)
        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
        expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    })

    it('persists the literal "system" string when the user picks System', () => {
        // Start from a non-system state so clicking System triggers a real change.
        window.localStorage.setItem(THEME_STORAGE_KEY, 'light')
        render(<ThemeToggle />)
        const system = screen.getByRole('radio', { name: /System/i }) as HTMLInputElement
        fireEvent.click(system)
        expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('system')
        // OS pref is dark in this test setup, so resolved data-theme should be dark.
        expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    })

    it('exposes a labelled radiogroup for screen readers', () => {
        render(<ThemeToggle />)
        expect(screen.getByRole('radiogroup', { name: 'Theme preference' })).toBeInTheDocument()
    })
})
