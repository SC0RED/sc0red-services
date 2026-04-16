import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PortfolioProgressStrip from '@/components/scan/PortfolioProgressStrip'

describe('PortfolioProgressStrip', () => {
    it('renders count label and percentage', () => {
        render(<PortfolioProgressStrip completedCount={5} totalCount={69} visible={true} />)
        expect(screen.getByText('5 of 69 done')).toBeInTheDocument()
        expect(screen.getByText('7%')).toBeInTheDocument()
    })

    it('renders nothing when visible is false', () => {
        const { container } = render(
            <PortfolioProgressStrip completedCount={5} totalCount={69} visible={false} />
        )
        expect(container.firstChild).toBeNull()
    })

    it('renders nothing when totalCount is 0', () => {
        const { container } = render(
            <PortfolioProgressStrip completedCount={0} totalCount={0} visible={true} />
        )
        expect(container.firstChild).toBeNull()
    })

    it('shows 100% when all complete', () => {
        render(<PortfolioProgressStrip completedCount={69} totalCount={69} visible={true} />)
        expect(screen.getByText('69 of 69 done')).toBeInTheDocument()
        expect(screen.getByText('100%')).toBeInTheDocument()
    })
})
