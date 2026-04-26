import { render, screen, act, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

import { ToastProvider, useToast } from '@/components/ui/Toast'

/**
 * A small helper that renders a button which dispatches whatever toast
 * action a test wants. Easier than threading a hook ref through the
 * tree.
 */
function ToastTrigger({ run }: { run: (toast: ReturnType<typeof useToast>) => void }) {
    const toast = useToast()
    return (
        <button type="button" onClick={() => run(toast)}>
            fire
        </button>
    )
}

function renderWithProvider(child: React.ReactNode) {
    return render(<ToastProvider>{child}</ToastProvider>)
}

describe('Toast / ToastProvider', () => {
    beforeEach(() => {
        vi.useFakeTimers()
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.restoreAllMocks()
    })

    describe('variants', () => {
        it('renders success toast with role="status"', () => {
            const { container } = renderWithProvider(<ToastTrigger run={(toast) => toast.success('Saved')} />)
            fireEvent.click(screen.getByText('fire'))
            expect(screen.getByText('Saved')).toBeInTheDocument()
            const toast = container.querySelector('[data-variant="success"]')
            expect(toast?.getAttribute('role')).toBe('status')
        })

        it('renders error toast with role="alert"', () => {
            const { container } = renderWithProvider(<ToastTrigger run={(toast) => toast.error('Boom')} />)
            fireEvent.click(screen.getByText('fire'))
            const toast = container.querySelector('[data-variant="error"]')
            expect(toast?.getAttribute('role')).toBe('alert')
        })

        it('renders info toast with role="status"', () => {
            const { container } = renderWithProvider(<ToastTrigger run={(toast) => toast.info('Heads up')} />)
            fireEvent.click(screen.getByText('fire'))
            expect(container.querySelector('[data-variant="info"]')?.getAttribute('role')).toBe('status')
        })

        it('renders loading toast with role="status"', () => {
            const { container } = renderWithProvider(
                <ToastTrigger run={(toast) => toast.loading('Working...')} />
            )
            fireEvent.click(screen.getByText('fire'))
            expect(container.querySelector('[data-variant="loading"]')?.getAttribute('role')).toBe('status')
        })

        it('renders description when provided', () => {
            renderWithProvider(<ToastTrigger run={(toast) => toast.success('Saved', 'All changes synced')} />)
            fireEvent.click(screen.getByText('fire'))
            expect(screen.getByText('Saved')).toBeInTheDocument()
            expect(screen.getByText('All changes synced')).toBeInTheDocument()
        })
    })

    describe('auto-dismiss', () => {
        it('success toast auto-dismisses after 4 seconds', () => {
            renderWithProvider(<ToastTrigger run={(toast) => toast.success('bye')} />)
            fireEvent.click(screen.getByText('fire'))
            expect(screen.getByText('bye')).toBeInTheDocument()
            act(() => {
                vi.advanceTimersByTime(4000)
            })
            expect(screen.queryByText('bye')).not.toBeInTheDocument()
        })

        it('info toast auto-dismisses after 4 seconds', () => {
            renderWithProvider(<ToastTrigger run={(toast) => toast.info('fyi')} />)
            fireEvent.click(screen.getByText('fire'))
            act(() => {
                vi.advanceTimersByTime(4000)
            })
            expect(screen.queryByText('fyi')).not.toBeInTheDocument()
        })

        it('error toast does NOT auto-dismiss', () => {
            renderWithProvider(<ToastTrigger run={(toast) => toast.error('stays')} />)
            fireEvent.click(screen.getByText('fire'))
            act(() => {
                vi.advanceTimersByTime(10_000)
            })
            expect(screen.getByText('stays')).toBeInTheDocument()
        })

        it('loading toast does NOT auto-dismiss', () => {
            renderWithProvider(<ToastTrigger run={(toast) => toast.loading('working')} />)
            fireEvent.click(screen.getByText('fire'))
            act(() => {
                vi.advanceTimersByTime(10_000)
            })
            expect(screen.getByText('working')).toBeInTheDocument()
        })
    })

    describe('dismiss', () => {
        it('close button removes the toast', () => {
            renderWithProvider(<ToastTrigger run={(toast) => toast.error('close me')} />)
            fireEvent.click(screen.getByText('fire'))
            expect(screen.getByText('close me')).toBeInTheDocument()
            fireEvent.click(screen.getByLabelText('Dismiss notification'))
            expect(screen.queryByText('close me')).not.toBeInTheDocument()
        })

        it('toast.dismiss(id) removes only the matching toast', () => {
            // Capture two ids and dismiss only the first via two clicks on
            // the same trigger — keeps everything inside one provider.
            let firstId = ''
            let dispatchedSecond = false
            renderWithProvider(
                <ToastTrigger
                    run={(toast) => {
                        if (!firstId) {
                            firstId = toast.success('first')
                            toast.success('second')
                            dispatchedSecond = true
                            return
                        }
                        toast.dismiss(firstId)
                    }}
                />
            )
            fireEvent.click(screen.getByText('fire'))
            expect(dispatchedSecond).toBe(true)
            expect(screen.getByText('first')).toBeInTheDocument()
            expect(screen.getByText('second')).toBeInTheDocument()

            fireEvent.click(screen.getByText('fire'))
            expect(screen.queryByText('first')).not.toBeInTheDocument()
            expect(screen.getByText('second')).toBeInTheDocument()
        })
    })

    describe('update / promote', () => {
        it('toast.update promotes loading → success in place', () => {
            let loadingId = ''
            renderWithProvider(
                <ToastTrigger
                    run={(toast) => {
                        if (!loadingId) {
                            loadingId = toast.loading('Re-analyzing...')
                            return
                        }
                        toast.update(loadingId, {
                            variant: 'success',
                            message: 'Re-analysis queued',
                        })
                    }}
                />
            )
            fireEvent.click(screen.getByText('fire'))
            expect(screen.getByText('Re-analyzing...')).toBeInTheDocument()
            // Single toast item in the DOM
            expect(document.querySelectorAll('[data-variant]').length).toBe(1)

            fireEvent.click(screen.getByText('fire'))
            expect(screen.queryByText('Re-analyzing...')).not.toBeInTheDocument()
            expect(screen.getByText('Re-analysis queued')).toBeInTheDocument()
            // Still a single toast — promoted in place, not duplicated
            expect(document.querySelectorAll('[data-variant]').length).toBe(1)
            expect(document.querySelector('[data-variant="success"]')).toBeInTheDocument()
        })
    })

    describe('stacking', () => {
        it('multiple toasts render stacked', () => {
            renderWithProvider(
                <ToastTrigger
                    run={(toast) => {
                        toast.success('one')
                        toast.success('two')
                        toast.success('three')
                    }}
                />
            )
            fireEvent.click(screen.getByText('fire'))
            expect(screen.getByText('one')).toBeInTheDocument()
            expect(screen.getByText('two')).toBeInTheDocument()
            expect(screen.getByText('three')).toBeInTheDocument()
            expect(document.querySelectorAll('[data-variant="success"]').length).toBe(3)
        })

        it('viewport renders inside an aria-live region', () => {
            const { container } = renderWithProvider(<ToastTrigger run={(toast) => toast.success('hi')} />)
            fireEvent.click(screen.getByText('fire'))
            const viewport = container.querySelector('.toast-viewport')
            expect(viewport?.getAttribute('aria-live')).toBe('polite')
        })
    })

    describe('contract', () => {
        it('useToast throws when used outside ToastProvider', () => {
            // Suppress the React error-boundary console noise for this test
            const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
            expect(() => render(<ToastTrigger run={(toast) => toast.success('x')} />)).toThrow(
                /useToast must be used within a <ToastProvider>/
            )
            errorSpy.mockRestore()
        })
    })
})
