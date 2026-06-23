import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'

import ProvideSourceUrlForm from '@/components/scan/ProvideSourceUrlForm'

describe('ProvideSourceUrlForm', () => {
    it('renders collapsed as a toggle button', () => {
        render(<ProvideSourceUrlForm onProvideSourceUrl={vi.fn()} />)
        expect(screen.getByText('+ Provide a page URL')).toBeInTheDocument()
        expect(screen.queryByLabelText('Portfolio page URL')).not.toBeInTheDocument()
    })

    it('expands to a form with expectation-setting copy', () => {
        render(<ProvideSourceUrlForm onProvideSourceUrl={vi.fn()} />)
        fireEvent.click(screen.getByText('+ Provide a page URL'))
        expect(screen.getByLabelText('Portfolio page URL')).toBeInTheDocument()
        // Honest expectation-setting about client-side-rendered pages.
        expect(screen.getByText(/builds its list in the browser after load/)).toBeInTheDocument()
    })

    it('submits a normalized URL and collapses', () => {
        const onProvideSourceUrl = vi.fn()
        render(<ProvideSourceUrlForm onProvideSourceUrl={onProvideSourceUrl} />)
        fireEvent.click(screen.getByText('+ Provide a page URL'))
        // Bare hostname — the normaliser prepends https://.
        fireEvent.change(screen.getByLabelText('Portfolio page URL'), {
            target: { value: 'firm.com/portfolio' },
        })
        fireEvent.click(screen.getByText('Fetch from this page'))

        expect(onProvideSourceUrl).toHaveBeenCalledWith('https://firm.com/portfolio')
        // Collapses back to the toggle button.
        expect(screen.getByText('+ Provide a page URL')).toBeInTheDocument()
        expect(screen.queryByLabelText('Portfolio page URL')).not.toBeInTheDocument()
    })

    it('shows an error and does not submit when the field is empty', () => {
        const onProvideSourceUrl = vi.fn()
        render(<ProvideSourceUrlForm onProvideSourceUrl={onProvideSourceUrl} />)
        fireEvent.click(screen.getByText('+ Provide a page URL'))
        fireEvent.click(screen.getByText('Fetch from this page'))

        expect(screen.getByText('Enter the URL of a page that lists the portfolio.')).toBeInTheDocument()
        expect(onProvideSourceUrl).not.toHaveBeenCalled()
    })

    it('rejects a malformed URL', () => {
        const onProvideSourceUrl = vi.fn()
        render(<ProvideSourceUrlForm onProvideSourceUrl={onProvideSourceUrl} />)
        fireEvent.click(screen.getByText('+ Provide a page URL'))
        fireEvent.change(screen.getByLabelText('Portfolio page URL'), {
            target: { value: 'notaurl' },
        })
        fireEvent.click(screen.getByText('Fetch from this page'))

        expect(onProvideSourceUrl).not.toHaveBeenCalled()
        // Still showing the form (not collapsed) with an inline error.
        expect(screen.getByLabelText('Portfolio page URL')).toBeInTheDocument()
    })

    it('collapses without submitting on Cancel', () => {
        const onProvideSourceUrl = vi.fn()
        render(<ProvideSourceUrlForm onProvideSourceUrl={onProvideSourceUrl} />)
        fireEvent.click(screen.getByText('+ Provide a page URL'))
        fireEvent.click(screen.getByText('Cancel'))

        expect(onProvideSourceUrl).not.toHaveBeenCalled()
        expect(screen.getByText('+ Provide a page URL')).toBeInTheDocument()
        expect(screen.queryByLabelText('Portfolio page URL')).not.toBeInTheDocument()
    })
})
