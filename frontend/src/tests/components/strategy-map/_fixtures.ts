import type { StrategyMap } from '@/lib/types/api'

/**
 * Shared full-data StrategyMap fixture used by the strategy-map RTL
 * tests. Mirrors the canned shape produced by the backend's 7-step
 * generation chain.
 */
export const fullStrategyMap: StrategyMap = {
    vision: {
        statement: 'To be the most appetizing convenience retailer',
        synthesised: false,
        rationale: 'Verbatim from the company brand materials.',
    },
    mission: {
        statement: 'Provide convenient food, beverages, and fuel to commuters.',
        synthesised: true,
        rationale: 'Synthesised from public store-locator content.',
    },
    valueProposition: {
        primary: 'customer_intimacy',
        secondary: null,
        rationale: 'Public materials emphasise associate friendliness and brand experience.',
        exemplar_company: 'Wawa',
    },
    strategicPriorities: [
        {
            name: 'Grow Through Foodservice',
            result: 'Best-in-class signature food platform driving same-store growth.',
        },
        {
            name: 'Deliver Convenience and Value',
            result: 'Industry-leading customer perception of speed and value.',
        },
    ],
    financial: {
        objectives: [
            {
                id: 'F1',
                title: 'Grow profitable revenue across markets',
                definition:
                    'We will grow same-segment revenue by deepening engagement with current customers and entering adjacent markets, with year-over-year revenue growth as the primary measure of expansion success.',
                category: 'revenue_growth',
                confidence: 'HIGH',
            },
            {
                id: 'F2',
                title: 'Drive operational efficiency',
                definition:
                    'We will improve cost-to-serve metrics by automating routine operations, reducing waste in supply chain, and optimising labour scheduling against actual demand patterns.',
                category: 'productivity',
                confidence: 'MEDIUM',
            },
            {
                id: 'F3',
                title: 'Maximise return on invested capital',
                definition:
                    'We will allocate capital toward the highest-return store formats and geographies, retiring or repositioning stores below threshold IRR within a defined refresh cycle.',
                category: 'productivity',
                confidence: 'MEDIUM',
            },
        ],
    },
    customer: {
        objectives: [
            {
                id: 'C1',
                title: 'Offer me fresh products in a friendly environment',
                definition:
                    'I rely on this brand for fast, friendly service and quality products. I value the consistent in-store experience and the friendly associates who treat me as a regular.',
                panel: 'consumer',
                confidence: 'HIGH',
            },
            {
                id: 'C2',
                title: 'Recognise my loyalty and reward me for it',
                definition:
                    'I expect the loyalty programme to acknowledge my repeated visits with meaningful rewards that I actually use, not just promotional clutter.',
                panel: 'consumer',
                confidence: 'MEDIUM',
            },
            {
                id: 'C3',
                title: 'Make my visit fast and convenient',
                definition:
                    'I want to get in, get what I need, and get out. The store layout, checkout speed, and service at the counter all contribute to whether I will stop here next time.',
                panel: 'consumer',
                confidence: 'HIGH',
            },
        ],
    },
    internalProcesses: {
        themes: [
            {
                name: 'Grow Through Foodservice',
                supports_financial_objectives: ['F1'],
                objectives: [
                    {
                        id: 'I1.1',
                        title: 'Develop signature food and beverage offers',
                        definition:
                            'We will create and improve fresh food and beverage offers that differentiate the brand and grow basket size, with regular product platform reviews.',
                        category: 'innovation',
                        confidence: 'HIGH',
                    },
                ],
            },
            {
                name: 'Deliver Convenience and Value',
                supports_financial_objectives: ['F1', 'F2'],
                objectives: [
                    {
                        id: 'I2.1',
                        title: 'Improve end-to-end process throughput',
                        definition:
                            'We will continuously improve the throughput, quality, and cost of our end-to-end processes through a disciplined data-driven approach.',
                        category: 'operational_excellence',
                        confidence: 'HIGH',
                    },
                ],
            },
        ],
    },
    organizationalCapacity: {
        people: {
            id: 'O.P',
            title: 'Develop our associates as brand ambassadors',
            definition:
                'We will invest in associate development through structured training, succession planning, and a culture of ownership.',
            confidence: 'MEDIUM',
        },
        technology: {
            id: 'O.T',
            title: 'Deliver reliable systems and data-driven insight',
            definition:
                'We will provide consistently reliable technical products and support services, valuable insights for forward-looking decisions.',
            confidence: 'MEDIUM',
        },
        culture: {
            id: 'O.C',
            title: 'Live our values in every interaction',
            definition:
                'Our values are the foundation of how we work. We will live them consistently across the organisation.',
            confidence: 'LOW',
        },
    },
    arrows: [
        {
            from: 'O.P',
            to: 'I1.1',
            hypothesis:
                'Investing in associate development enables higher-quality execution of new food platforms.',
        },
        {
            from: 'I1.1',
            to: 'C1',
            hypothesis:
                'Signature food platforms drive the customer perception of fresh, friendly experience.',
        },
        {
            from: 'C1',
            to: 'F1',
            hypothesis: 'A delighted, returning customer drives same-store revenue growth.',
        },
        {
            from: 'I2.1',
            to: 'F2',
            hypothesis: 'Process improvements lower cost-to-serve, contributing to operational efficiency.',
        },
        {
            from: 'O.T',
            to: 'I2.1',
            hypothesis: 'Reliable systems enable disciplined process improvement.',
        },
    ],
    coreValues: {
        values: ['Care for customers', 'Respect for associates', 'Continuous improvement'],
        synthesised: true,
        rationale: 'Synthesised from public materials.',
    },
}
