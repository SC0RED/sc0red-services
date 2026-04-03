import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import ScanProgressPhase from '@/components/scan/ScanProgressPhase'

describe('ScanProgressPhase', () => {
    it('shows analyzing title in analyzing phase', () => {
        render(<ScanProgressPhase phase="analyzing" progress={30} progressLabel="Scraping website..." />)
        expect(screen.getByText('Analyzing...')).toBeInTheDocument()
    })

    it('shows running portfolio title in running phase', () => {
        render(<ScanProgressPhase phase="running" progress={50} progressLabel="Processing..." />)
        expect(screen.getByText('Running Portfolio Analysis...')).toBeInTheDocument()
    })

    it('displays progress label', () => {
        render(<ScanProgressPhase phase="analyzing" progress={45} progressLabel="Assessing risks..." />)
        expect(screen.getByText('Assessing risks...')).toBeInTheDocument()
    })

    it('displays progress percentage', () => {
        render(<ScanProgressPhase phase="analyzing" progress={67} progressLabel="" />)
        expect(screen.getByText('67% complete')).toBeInTheDocument()
    })

    it('rounds progress percentage', () => {
        render(<ScanProgressPhase phase="running" progress={33.7} progressLabel="" />)
        expect(screen.getByText('34% complete')).toBeInTheDocument()
    })

    it('shows help text about keeping page open', () => {
        render(<ScanProgressPhase phase="analyzing" progress={0} progressLabel="" />)
        expect(screen.getByText(/This typically takes 1–3 minutes/)).toBeInTheDocument()
    })
})
