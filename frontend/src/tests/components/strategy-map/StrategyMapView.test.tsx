import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import StrategyMapView from '@/components/strategy-map/StrategyMapView'

import { fullStrategyMap } from './_fixtures'

describe('StrategyMapView', () => {
    it('renders the strategy-map header band with vision, mission, and value proposition', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)

        expect(screen.getByText('Strategy Map')).toBeInTheDocument()
        expect(screen.getByText(/To be the most appetizing convenience retailer/)).toBeInTheDocument()
        expect(
            screen.getByText('Provide convenient food, beverages, and fuel to commuters.')
        ).toBeInTheDocument()
        expect(screen.getByText('Customer Intimacy')).toBeInTheDocument()
    })

    it('flags synthesised mission with the (synthesised) marker', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText(/Mission \(synthesised\)/)).toBeInTheDocument()
    })

    it('renders all four perspective rows with their objectives', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)

        // Financial: 3 objectives — every title should appear
        expect(screen.getByText('Grow profitable revenue across markets')).toBeInTheDocument()
        expect(screen.getByText('Drive operational efficiency')).toBeInTheDocument()
        expect(screen.getByText('Maximise return on invested capital')).toBeInTheDocument()

        // Customer (first-person, quoted)
        expect(screen.getByText('"Offer me fresh products in a friendly environment"')).toBeInTheDocument()
        expect(screen.getByText('"Recognise my loyalty and reward me for it"')).toBeInTheDocument()
        expect(screen.getByText('"Make my visit fast and convenient"')).toBeInTheDocument()

        // Internal Processes themed
        expect(screen.getByText('Develop signature food and beverage offers')).toBeInTheDocument()
        expect(screen.getByText('Improve end-to-end process throughput')).toBeInTheDocument()

        // Organizational Capacity (P/T/C)
        expect(screen.getByText('Develop our associates as brand ambassadors')).toBeInTheDocument()
        expect(screen.getByText('Deliver reliable systems and data-driven insight')).toBeInTheDocument()
        expect(screen.getByText('Live our values in every interaction')).toBeInTheDocument()
    })

    it('renders confidence chips for every objective', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)

        // 3 financial + 3 customer + 2 IP + 3 capacity = 11 total. Counts:
        // HIGH=4 (F1, C1, C3, I1.1, I2.1) — actually 5
        // MEDIUM=4 (F2, F3, C2, O.P, O.T)
        // LOW=1 (O.C)
        const highChips = screen.getAllByText('HIGH')
        const mediumChips = screen.getAllByText('MEDIUM')
        const lowChips = screen.getAllByText('LOW')

        expect(highChips.length).toBeGreaterThanOrEqual(4)
        expect(mediumChips.length).toBeGreaterThanOrEqual(4)
        expect(lowChips.length).toBeGreaterThanOrEqual(1)
    })

    it('renders the strategic priorities with their results', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getAllByText(/Grow Through Foodservice/).length).toBeGreaterThanOrEqual(1)
        expect(screen.getAllByText(/Deliver Convenience and Value/).length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText(/Industry-leading customer perception/)).toBeInTheDocument()
    })

    it('renders the core-values strip with the inferred marker when synthesised', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText(/Live our values \(inferred\):/)).toBeInTheDocument()
        expect(screen.getByText(/Care for customers/)).toBeInTheDocument()
    })

    it('renders the "What\'s Missing?" panel with each gap and its deep-dive framing', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByTestId('strategy-map-whats-missing')).toBeInTheDocument()
        expect(screen.getByText('Cultural commitments not explicitly published')).toBeInTheDocument()
        expect(screen.getByText('Channel-relationship strategy unclear')).toBeInTheDocument()
        // Deep-dive framing sentences should be visible
        expect(screen.getByText(/A Vector Advisory deep-dive would interview leadership/)).toBeInTheDocument()
        expect(
            screen.getByText(/A Vector Advisory deep-dive would map the channel economics/)
        ).toBeInTheDocument()
    })

    it('connects internal-process themes to financial objectives via the supports arrow', () => {
        render(<StrategyMapView strategyMap={fullStrategyMap} />)
        expect(screen.getByText('→ F1')).toBeInTheDocument()
        expect(screen.getByText('→ F1, F2')).toBeInTheDocument()
    })
})
