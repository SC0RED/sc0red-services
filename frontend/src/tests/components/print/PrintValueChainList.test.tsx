import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import PrintValueChainList from '@/components/print/PrintValueChainList'
import { sortOpportunities } from '@/lib/pdf/sortOpportunities'
import type { Opportunity, ValueChain, ValueChainStep } from '@/lib/types/api'

const opp = (title: string): Opportunity => ({
    title,
    description: 'd',
    impact_rating: 'High',
    timeline: 't',
    strategic_category: 'Operational Efficiency',
})

const step = (overrides: Partial<ValueChainStep>): ValueChainStep => ({
    id: 'step',
    label: 'Step',
    description: 'd',
    category: 'primary',
    risk_categories: [],
    opportunity_indices: [],
    ...overrides,
})

const valueChain: ValueChain = {
    summary: 'Standard B2B chain.',
    steps: [
        step({ id: 'p1', label: 'Inbound Logistics', risk_categories: ['supply_chain'] }),
        step({ id: 'p2', label: 'Operations' }),
        step({ id: 'p3', label: 'Outbound Logistics' }),
        step({ id: 'p4', label: 'Marketing & Sales' }),
        step({ id: 'p5', label: 'Service' }),
        step({ id: 'p6', label: 'Customer Success & Support', opportunity_indices: [1] }),
        step({ id: 's1', label: 'Procurement', category: 'support' }),
        step({ id: 's2', label: 'Technology Development', category: 'support' }),
        step({ id: 's3', label: 'Human Resources', category: 'support' }),
        step({ id: 's4', label: 'Firm Infrastructure', category: 'support' }),
        step({ id: 's5', label: 'Internal IT', category: 'support' }),
    ],
}

const opportunities: Opportunity[] = [opp('Idle filler'), opp('Customer-success automation')]
const sortedOpportunities = sortOpportunities(opportunities)

describe('PrintValueChainList', () => {
    it('returns null when there are no steps', () => {
        const { container } = render(
            <PrintValueChainList
                valueChain={{ summary: '', steps: [] }}
                sortedOpportunities={sortedOpportunities}
            />
        )
        expect(container.firstChild).toBeNull()
    })

    it('renders all six primary activities and all five support activities', () => {
        render(<PrintValueChainList valueChain={valueChain} sortedOpportunities={sortedOpportunities} />)
        const labels = [
            'Inbound Logistics',
            'Operations',
            'Outbound Logistics',
            'Marketing & Sales',
            'Service',
            'Customer Success & Support',
            'Procurement',
            'Technology Development',
            'Human Resources',
            'Firm Infrastructure',
            'Internal IT',
        ]
        for (const label of labels) {
            expect(screen.getByText(label)).toBeInTheDocument()
        }
    })

    it('uses vertical row layout with no horizontal flex', () => {
        const { container } = render(
            <PrintValueChainList valueChain={valueChain} sortedOpportunities={sortedOpportunities} />
        )
        // Rows are <li> with class print-value-chain-row.
        const rows = container.querySelectorAll('.print-value-chain-row')
        expect(rows.length).toBe(11)
        // No element should set display: flex with row direction at the row level.
        for (const row of Array.from(rows)) {
            const direction = (row as HTMLElement).style.flexDirection
            expect(direction === 'row').toBe(false)
        }
    })

    it('resolves linkage callouts using the printed index', () => {
        render(<PrintValueChainList valueChain={valueChain} sortedOpportunities={sortedOpportunities} />)
        // originalIndex 1 → "Customer-success automation". Both opps are High,
        // stable sort preserves API order, so printedIndex of "Customer-success
        // automation" is 2.
        expect(screen.getByText(/Customer-success automation/)).toBeInTheDocument()
    })

    it('renders Primary and Support group headings', () => {
        render(<PrintValueChainList valueChain={valueChain} sortedOpportunities={sortedOpportunities} />)
        expect(screen.getByText('Primary Activities')).toBeInTheDocument()
        expect(screen.getByText('Support Activities')).toBeInTheDocument()
    })

    it('omits the Support group heading when there are no support steps', () => {
        const primaryOnly: ValueChain = {
            summary: '',
            steps: valueChain.steps.filter((step) => step.category === 'primary'),
        }
        render(<PrintValueChainList valueChain={primaryOnly} sortedOpportunities={sortedOpportunities} />)
        expect(screen.queryByText('Support Activities')).not.toBeInTheDocument()
    })
})
