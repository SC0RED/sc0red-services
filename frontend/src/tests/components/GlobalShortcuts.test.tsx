import { fireEvent, screen, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

import GlobalShortcuts from '@/components/GlobalShortcuts'
import { renderWithProviders } from '@/tests/test-utils'

const mockPush = vi.fn()
let mockPathname = '/dashboard'

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: mockPush, refresh: vi.fn() }),
    usePathname: () => mockPathname,
}))

describe('GlobalShortcuts', () => {
    beforeEach(() => {
        // Real timers by default — `waitFor` and React state flush rely on
        // real microtask scheduling. Tests that need to advance the chord
        // timeout opt into fake timers explicitly.
        vi.clearAllMocks()
        mockPathname = '/dashboard'
        global.fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ analyses: [], recentScans: [] }),
        })
    })

    function pressKey(key: string, opts: { metaKey?: boolean; ctrlKey?: boolean; shiftKey?: boolean } = {}) {
        fireEvent.keyDown(window, { key, ...opts })
    }

    describe('Cmd-K opens palette', () => {
        it('opens the palette when Cmd+K is pressed', async () => {
            renderWithProviders(<GlobalShortcuts />)
            expect(screen.queryByPlaceholderText(/Search companies/)).not.toBeInTheDocument()

            pressKey('k', { metaKey: true })

            await waitFor(() => {
                expect(screen.getByPlaceholderText(/Search companies/)).toBeInTheDocument()
            })
        })

        it('opens with Ctrl+K (Windows/Linux)', async () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('k', { ctrlKey: true })

            await waitFor(() => {
                expect(screen.getByPlaceholderText(/Search companies/)).toBeInTheDocument()
            })
        })

        it('toggles closed when Cmd+K pressed while open', async () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('k', { metaKey: true })
            await waitFor(() => screen.getByPlaceholderText(/Search companies/))

            pressKey('k', { metaKey: true })

            await waitFor(() => {
                expect(screen.queryByPlaceholderText(/Search companies/)).not.toBeInTheDocument()
            })
        })
    })

    describe('? opens shortcuts modal', () => {
        it('opens the shortcuts help modal when ? is pressed', async () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('?')
            await waitFor(() => {
                expect(screen.getByText('Keyboard shortcuts')).toBeInTheDocument()
            })
        })

        it('does not open when typing in an input', () => {
            renderWithProviders(
                <>
                    <input data-testid="some-input" />
                    <GlobalShortcuts />
                </>
            )
            const input = screen.getByTestId('some-input')
            input.focus()
            fireEvent.keyDown(input, { key: '?' })
            expect(screen.queryByText('Keyboard shortcuts')).not.toBeInTheDocument()
        })
    })

    describe('g-prefix navigation chords', () => {
        it('g d navigates to /dashboard', () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('g')
            pressKey('d')
            expect(mockPush).toHaveBeenCalledWith('/dashboard')
        })

        it('g a navigates to /analyses', () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('g')
            pressKey('a')
            expect(mockPush).toHaveBeenCalledWith('/analyses')
        })

        it('g s navigates to /scan/new', () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('g')
            pressKey('s')
            expect(mockPush).toHaveBeenCalledWith('/scan/new')
        })

        it('g t navigates to /team', () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('g')
            pressKey('t')
            expect(mockPush).toHaveBeenCalledWith('/team')
        })

        it('g c navigates to /settings', () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('g')
            pressKey('c')
            expect(mockPush).toHaveBeenCalledWith('/settings')
        })

        it('g i navigates to /connect', () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('g')
            pressKey('i')
            expect(mockPush).toHaveBeenCalledWith('/connect')
        })

        it('chord resets after 1 second timeout', () => {
            vi.useFakeTimers()
            try {
                renderWithProviders(<GlobalShortcuts />)
                pressKey('g')
                // Wait past the chord timeout
                vi.advanceTimersByTime(1100)
                pressKey('d')
                expect(mockPush).not.toHaveBeenCalled()
            } finally {
                vi.useRealTimers()
            }
        })

        it('chord ignored when typing in an input', () => {
            renderWithProviders(
                <>
                    <input data-testid="some-input" />
                    <GlobalShortcuts />
                </>
            )
            const input = screen.getByTestId('some-input')
            input.focus()
            fireEvent.keyDown(input, { key: 'g' })
            fireEvent.keyDown(input, { key: 'd' })
            expect(mockPush).not.toHaveBeenCalled()
        })

        it('unknown second-key resets chord without navigating', () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('g')
            pressKey('x')
            expect(mockPush).not.toHaveBeenCalled()
            // Chord should be reset — pressing 'd' alone shouldn't fire
            pressKey('d')
            expect(mockPush).not.toHaveBeenCalled()
        })
    })

    describe('/ focuses search on /analyses', () => {
        it('focuses the search input when on /analyses', () => {
            mockPathname = '/analyses'
            const focus = vi.fn()
            // Stub a search input on the page
            const fakeInput = document.createElement('input')
            fakeInput.setAttribute('aria-label', 'Search analyses')
            fakeInput.focus = focus
            document.body.appendChild(fakeInput)

            renderWithProviders(<GlobalShortcuts />)
            pressKey('/')

            expect(focus).toHaveBeenCalled()
            document.body.removeChild(fakeInput)
        })

        it('does nothing when not on /analyses', () => {
            mockPathname = '/dashboard'
            renderWithProviders(<GlobalShortcuts />)
            pressKey('/')
            // No throw, no router.push
            expect(mockPush).not.toHaveBeenCalled()
        })
    })

    describe('Esc closes topmost modal', () => {
        it('closes the palette when palette is open', async () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('k', { metaKey: true })
            await waitFor(() => screen.getByPlaceholderText(/Search companies/))

            pressKey('Escape')

            await waitFor(() => {
                expect(screen.queryByPlaceholderText(/Search companies/)).not.toBeInTheDocument()
            })
        })

        it('closes the shortcuts modal when only that is open', async () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('?')
            await waitFor(() => screen.getByText('Keyboard shortcuts'))

            pressKey('Escape')

            await waitFor(() => {
                expect(screen.queryByText('Keyboard shortcuts')).not.toBeInTheDocument()
            })
        })

        it('Esc with no modal open does not crash', () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('Escape')
            // No assertion needed beyond no-throw
        })
    })

    describe('chord suppression while modals open', () => {
        it('does not navigate when palette is open and g d is pressed', async () => {
            renderWithProviders(<GlobalShortcuts />)
            pressKey('k', { metaKey: true })
            await waitFor(() => screen.getByPlaceholderText(/Search companies/))

            // Palette is open — chord should NOT register on the global handler.
            // (cmdk's input has its own focus, so g/d would type into it)
            pressKey('g')
            pressKey('d')
            expect(mockPush).not.toHaveBeenCalled()
        })
    })
})
