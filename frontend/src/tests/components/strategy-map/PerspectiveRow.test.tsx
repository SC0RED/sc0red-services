import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import {
    CustomerPerspectiveRow,
    FinancialPerspectiveRow,
    InternalProcessesPerspectiveRow,
    OrganizationalCapacityRow,
} from '@/components/strategy-map/PerspectiveRow'

import { fullStrategyMap } from './_fixtures'

describe('FinancialPerspectiveRow', () => {
    it('renders all financial objectives in a flat grid', () => {
        render(<FinancialPerspectiveRow objectives={fullStrategyMap.financial.objectives} />)
        expect(screen.getByText('Financial')).toBeInTheDocument()
        expect(screen.getByText('Grow profitable revenue across markets')).toBeInTheDocument()
        expect(screen.getByText('Drive operational efficiency')).toBeInTheDocument()
        expect(screen.getByText('Maximise return on invested capital')).toBeInTheDocument()
    })
})

describe('CustomerPerspectiveRow', () => {
    it('renders objectives with first-person customer-voice quotes', () => {
        render(<CustomerPerspectiveRow objectives={fullStrategyMap.customer.objectives} />)
        expect(screen.getByText('Customer')).toBeInTheDocument()
        expect(screen.getByText('"Offer me fresh products in a friendly environment"')).toBeInTheDocument()
        expect(screen.getByText('"Recognise my loyalty and reward me for it"')).toBeInTheDocument()
    })

    it('shows the connector phrase above the row', () => {
        render(<CustomerPerspectiveRow objectives={fullStrategyMap.customer.objectives} />)
        expect(screen.getByText(/Which simplify the lives of our/)).toBeInTheDocument()
    })
})

describe('InternalProcessesPerspectiveRow', () => {
    it('renders themes with their objective lists and the supports-financial pointer', () => {
        render(<InternalProcessesPerspectiveRow themes={fullStrategyMap.internalProcesses.themes} />)
        // Theme name appears in the IP row (the same name also appears in the
        // strategic-priorities band rendered higher up — but this row only
        // includes the name once, in the theme header).
        expect(screen.getAllByText(/Grow Through Foodservice/i).length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText('→ F1')).toBeInTheDocument()
        expect(screen.getByText('→ F1, F2')).toBeInTheDocument()
        // Each theme's objectives appear
        expect(screen.getByText('Develop signature food and beverage offers')).toBeInTheDocument()
        expect(screen.getByText('Improve end-to-end process throughput')).toBeInTheDocument()
    })
})

describe('OrganizationalCapacityRow', () => {
    it('renders the People / Technology / Culture triad', () => {
        render(<OrganizationalCapacityRow perspective={fullStrategyMap.organizationalCapacity} />)
        expect(screen.getByText('People')).toBeInTheDocument()
        expect(screen.getByText('Technology')).toBeInTheDocument()
        expect(screen.getByText('Culture')).toBeInTheDocument()
        expect(screen.getByText('Develop our associates as brand ambassadors')).toBeInTheDocument()
        expect(screen.getByText('Deliver reliable systems and data-driven insight')).toBeInTheDocument()
        expect(screen.getByText('Live our values in every interaction')).toBeInTheDocument()
    })
})
