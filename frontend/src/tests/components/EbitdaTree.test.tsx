/**
 * Tests for the static-waterfall ``EbitdaTree`` renderer.
 *
 * Renderer history:
 *   - ``redesign-ebitda-impact-model`` replaced a React Flow canvas
 *     with a static vertical waterfall.
 *   - ``compact-ebitda-bands`` collapsed parent cards into band
 *     headers and leaf cards into compact chips arranged horizontally
 *     inside each band.
 *
 * These tests pin the resulting spec requirements:
 *   - Five band rows in P&L order inside a single ``<ol>``.
 *   - Four connectors labelled ``minus``, ``equals``, ``minus``, ``equals``
 *     in that order, each with the label exposed as plain text.
 *   - No pan / zoom / fit / expand controls in the DOM.
 *   - Container height equals content height (no fixed-height canvas).
 *   - Semantic HTML: ``<section>`` with an accessible name, leaves
 *     under each parent grouped in a single ``<ul>`` with a
 *     parent-referencing ``aria-label`` and ``flex-direction: row`` +
 *     ``flex-wrap: wrap`` so chips flow horizontally and wrap on
 *     narrow viewports.
 *   - Mobile (375 px): no horizontal scroll on the waterfall.
 *   - Confidence chip + opportunity-link affordance preserved.
 */

import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'

import EbitdaTree from '@/components/EbitdaTree'
import type { EbitdaNode } from '@/lib/types/api'

// ── Fixtures ────────────────────────────────────────────────────────────────

/** Faithful five-subtotal P&L tree mirroring the backend's
 *  ``build_programmatic_ebitda_tree`` output: revenue, cogs,
 *  gross_profit, opex, ebitda — in P&L order. */
const FULL_TREE: EbitdaNode[] = [
    {
        id: 'revenue',
        label: 'Total Revenue',
        type: 'revenue',
        value_range: '$15M-$200M',
        parent_id: null,
        description: 'All revenue streams',
        linked_opportunity_indices: [],
        children: [
            {
                id: 'subscriptions',
                label: 'Subscriptions',
                type: 'revenue',
                value_range: '$12M-$160M',
                percentage_of_parent: 80,
                parent_id: 'revenue',
                description: 'SaaS subscriptions',
                linked_opportunity_indices: [0],
                children: [],
            },
            {
                id: 'professional_services',
                label: 'Professional Services',
                type: 'revenue',
                value_range: '$2M-$30M',
                percentage_of_parent: 15,
                parent_id: 'revenue',
                description: 'Professional services revenue',
                linked_opportunity_indices: [],
                children: [],
            },
        ],
    },
    {
        id: 'cogs',
        label: 'Cost of Revenue',
        type: 'cost',
        value_range: '$2M-$60M',
        parent_id: null,
        description: 'Direct costs',
        linked_opportunity_indices: [],
        children: [
            {
                id: 'cogs_support',
                label: 'Customer Support',
                type: 'cost',
                value_range: '$787K-$21M',
                percentage_of_parent: 35,
                parent_id: 'cogs',
                description: 'Support staffing + tooling',
                linked_opportunity_indices: [],
                children: [],
            },
        ],
    },
    {
        id: 'gross_profit',
        label: 'Gross Profit',
        type: 'subtotal',
        value_range: '$10M-$170M',
        parent_id: null,
        description: 'Revenue minus cost of revenue',
        linked_opportunity_indices: [],
        children: [],
    },
    {
        id: 'opex',
        label: 'Operating Expenses',
        type: 'cost',
        value_range: '$5M-$140M',
        parent_id: null,
        description: 'Sales/marketing + R&D + G&A',
        linked_opportunity_indices: [],
        children: [
            {
                id: 'opex_sm',
                label: 'Sales & Marketing',
                type: 'cost',
                value_range: '$2M-$63M',
                percentage_of_parent: 45,
                parent_id: 'opex',
                description: 'Sales + marketing spend',
                linked_opportunity_indices: [],
                children: [],
            },
        ],
    },
    {
        id: 'ebitda',
        label: 'EBITDA',
        type: 'subtotal',
        value_range: '$2M-$70M',
        parent_id: null,
        description: 'Earnings before interest, taxes, depreciation and amortisation',
        linked_opportunity_indices: [],
        children: [],
    },
]

// EbitdaTree now takes the full ``Opportunity[]`` shape (widened in
// the ``redesign-analysis-visuals`` P2 migration so the shared
// ``OpportunityDotStrip`` has the field set it needs).
import type { Opportunity } from '@/lib/types/api'

const OPPS: Opportunity[] = [
    {
        title: 'Upsell premium tier',
        description: 'Convert mid-tier users to premium with usage-based incentives.',
        impact_rating: 'High',
        timeline: 'Quick Win (1-3 months)',
        strategic_category: 'Operational Efficiency',
        value_lever: 'Revenue Side',
    },
]

// ── Spec requirement: vertical waterfall layout ─────────────────────────────

describe('EbitdaTree — static vertical waterfall (spec requirement 1)', () => {
    it('renders an <ol> with one entry per top-level subtotal in P&L order', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const waterfall = screen.getByTestId('ebitda-waterfall')
        expect(waterfall.tagName).toBe('OL')
        const rows = waterfall.querySelectorAll(':scope > li')
        expect(rows).toHaveLength(5)
        // P&L order: each row's first text content begins with the
        // subtotal label.
        const labels = Array.from(rows).map((li) => li.textContent ?? '')
        expect(labels[0]).toContain('Total Revenue')
        expect(labels[1]).toContain('Cost of Revenue')
        expect(labels[2]).toContain('Gross Profit')
        expect(labels[3]).toContain('Operating Expenses')
        expect(labels[4]).toContain('EBITDA')
    })

    it('does not use any React Flow / canvas / fixed-height container', () => {
        const { container } = render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        // No React Flow root.
        expect(container.querySelector('.react-flow')).toBeNull()
        expect(container.querySelector('[class*="xyflow"]')).toBeNull()
        // No element pinned to a 700px height (the old canvas anchor).
        const fixedHeight = Array.from(container.querySelectorAll<HTMLElement>('[style*="height"]')).filter(
            (el) =>
                /height\s*:\s*700px/i.test(el.getAttribute('style') ?? '') ||
                /height\s*:\s*100vh/i.test(el.getAttribute('style') ?? '')
        )
        expect(fixedHeight).toHaveLength(0)
    })
})

// ── Spec requirement: connector arithmetic labels ───────────────────────────

describe('EbitdaTree — subtotal connectors (spec requirement 2)', () => {
    it('renders four connectors in [minus, equals, minus, equals] order', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const waterfall = screen.getByTestId('ebitda-waterfall')
        const connectors = waterfall.querySelectorAll('[data-testid^="ebitda-connector-"]')
        expect(connectors).toHaveLength(4)
        const order = Array.from(connectors).map((el) => el.getAttribute('data-testid'))
        expect(order).toEqual([
            'ebitda-connector-minus',
            'ebitda-connector-equals',
            'ebitda-connector-minus',
            'ebitda-connector-equals',
        ])
    })

    it('connector labels are rendered as plain visible text (not only aria-label)', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const minusConnectors = screen.getAllByTestId('ebitda-connector-minus')
        const equalsConnectors = screen.getAllByTestId('ebitda-connector-equals')
        // Each connector renders its label as plain text inside the element.
        for (const el of minusConnectors) expect(el.textContent?.toLowerCase()).toContain('minus')
        for (const el of equalsConnectors) expect(el.textContent?.toLowerCase()).toContain('equals')
    })

    it('does not render a connector below the final subtotal', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const waterfall = screen.getByTestId('ebitda-waterfall')
        const rows = Array.from(waterfall.querySelectorAll(':scope > li'))
        const lastRow = rows[rows.length - 1]
        const connectorInLast = lastRow.querySelector('[data-testid^="ebitda-connector-"]')
        expect(connectorInLast).toBeNull()
    })
})

// ── Spec requirement: leaves under each parent ──────────────────────────────

describe('EbitdaTree — leaves under each parent (spec requirement 3)', () => {
    it("groups each parent's leaves in a <ul> with a parent-referencing aria-label", () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        // Total Revenue has 2 leaves in the fixture.
        const revenueLeafList = screen.getByRole('list', {
            name: 'Drivers of Total Revenue',
        })
        expect(revenueLeafList.tagName).toBe('UL')
        expect(revenueLeafList.querySelectorAll(':scope > li')).toHaveLength(2)

        // Cost of Revenue has 1 leaf.
        const cogsLeafList = screen.getByRole('list', {
            name: 'Drivers of Cost of Revenue',
        })
        expect(cogsLeafList.querySelectorAll(':scope > li')).toHaveLength(1)
    })

    it('does not emit a leaf <ul> for subtotals with no children', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        // Gross Profit + EBITDA have no children — no leaf list should
        // be rendered for them.
        expect(screen.queryByRole('list', { name: 'Drivers of Gross Profit' })).toBeNull()
        expect(screen.queryByRole('list', { name: 'Drivers of EBITDA' })).toBeNull()
    })

    it('renders each leaf with its label, value range, and percentage', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const revenueLeafList = screen.getByRole('list', {
            name: 'Drivers of Total Revenue',
        })
        expect(within(revenueLeafList).getByText('Subscriptions')).toBeInTheDocument()
        expect(within(revenueLeafList).getByText('$12M-$160M')).toBeInTheDocument()
        expect(within(revenueLeafList).getByText('80% of parent')).toBeInTheDocument()
    })
})

// ── Spec requirement: no pan / zoom / expand affordances ────────────────────

describe('EbitdaTree — no pan/zoom/expand controls (spec requirement 4)', () => {
    it('renders no Fit / Expand / zoom buttons', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        // None of the old React Flow control labels survive.
        expect(screen.queryByRole('button', { name: /fit/i })).toBeNull()
        expect(screen.queryByRole('button', { name: /expand/i })).toBeNull()
        expect(screen.queryByRole('button', { name: /close/i })).toBeNull()
        expect(screen.queryByLabelText(/zoom in/i)).toBeNull()
        expect(screen.queryByLabelText(/zoom out/i)).toBeNull()
        expect(screen.queryByLabelText(/fit view/i)).toBeNull()
    })

    it('does not render the legacy "Scroll to pan, pinch or use controls to zoom" legend', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        expect(screen.queryByText(/scroll to pan/i)).toBeNull()
        expect(screen.queryByText(/pinch.*zoom/i)).toBeNull()
    })
})

// ── Spec requirement: semantic HTML for screen readers ──────────────────────

describe('EbitdaTree — semantic HTML for screen readers (spec requirement 6)', () => {
    it('the section root is a <section> with an accessible name', () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const section = screen.getByRole('region', { name: /ebitda impact model/i })
        expect(section.tagName).toBe('SECTION')
    })

    it("the five subtotals are inside the section's ordered list", () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const section = screen.getByRole('region', { name: /ebitda impact model/i })
        const ol = section.querySelector('ol[data-testid="ebitda-waterfall"]')
        expect(ol).not.toBeNull()
        expect(ol!.querySelectorAll(':scope > li')).toHaveLength(5)
    })

    it("each parent's leaves are inside a <ul> referencing the parent", () => {
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        // All three parents with children get a leaf list; the names
        // unambiguously identify which parent each list belongs to.
        expect(screen.getByRole('list', { name: 'Drivers of Total Revenue' })).toBeInTheDocument()
        expect(screen.getByRole('list', { name: 'Drivers of Cost of Revenue' })).toBeInTheDocument()
        expect(screen.getByRole('list', { name: 'Drivers of Operating Expenses' })).toBeInTheDocument()
    })

    it('renders the five subtotal labels inside <h3> elements in P&L order', () => {
        // Per ``ebitda-impact-model`` §6, subtotal labels MUST render
        // in a heading element so a screen-reader user can navigate
        // the P&L sequence by heading. Leaves intentionally render
        // their labels OUTSIDE the heading scale to keep the page
        // headings to just the five subtotals.
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const headings = screen.getAllByRole('heading', { level: 3 })
        expect(headings.map((h) => h.textContent)).toEqual([
            'Total Revenue',
            'Cost of Revenue',
            'Gross Profit',
            'Operating Expenses',
            'EBITDA',
        ])
    })

    it('does NOT render leaf labels inside heading elements', () => {
        // Leaves render their labels in <div>, not <h3> — otherwise
        // the page-heading scale would balloon to 5 + ~7 = 12
        // headings, drowning out the P&L sequence.
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const headings = screen.getAllByRole('heading', { level: 3 })
        // No leaf label appears as a heading.
        for (const leaf of [
            'Subscriptions',
            'Professional Services',
            'Customer Support',
            'Sales & Marketing',
        ]) {
            expect(headings.some((h) => h.textContent === leaf)).toBe(false)
        }
    })
})

// ── Spec requirement: responsive without horizontal scroll ──────────────────

describe('EbitdaTree — responsive layout (spec requirement 3, mobile branch)', () => {
    it('uses flex-wrap on the parent/leaves container so leaves wrap below on narrow widths', () => {
        const { container } = render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        // Each subtotal row's content uses flex-wrap so the leaves
        // flow beside the parent on desktop and stack below on
        // mobile without any JS-driven layout. Assert the flex-wrap
        // attribute is present on the row content containers.
        const wrappers = Array.from(container.querySelectorAll<HTMLElement>('[style*="flex-wrap"]'))
        expect(wrappers.length).toBeGreaterThan(0)
        for (const el of wrappers) {
            const style = el.getAttribute('style') ?? ''
            // ``flex-wrap: wrap`` (or its shorthand inside ``flex``) is
            // required — the value MUST NOT be ``nowrap`` because that
            // would prevent the mobile-stack behaviour.
            expect(/flex-wrap\s*:\s*nowrap/i.test(style)).toBe(false)
        }
    })

    it('no element of the section forces horizontal scroll', () => {
        const { container } = render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        // Anti-regression guard: a future contributor adding
        // ``overflow-x: scroll`` or ``min-width: 800px`` to the
        // waterfall would break the mobile contract. Assert no element
        // inside the section pins a horizontal scroll.
        const offending = Array.from(container.querySelectorAll<HTMLElement>('*')).filter((el) => {
            const style = el.getAttribute('style') ?? ''
            return /overflow-x\s*:\s*scroll/i.test(style) || /overflow\s*:\s*scroll/i.test(style)
        })
        expect(offending).toHaveLength(0)
    })

    it("renders all of a parent's leaves inside a single flex-wrap <ul>", () => {
        // Per ``compact-ebitda-bands``: leaves are compact chips arranged
        // horizontally inside the band, NOT a vertical stack. Each
        // parent's leaf list is a single ``<ul>`` with ``flex-direction:
        // row`` + ``flex-wrap: wrap``. This regression pins that
        // structural contract so a future change can't accidentally
        // split a parent's leaves across multiple lists.
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const revenueLeafList = screen.getByRole('list', { name: 'Drivers of Total Revenue' })
        expect(revenueLeafList.tagName).toBe('UL')
        const style = revenueLeafList.getAttribute('style') ?? ''
        expect(/flex-direction\s*:\s*row/i.test(style)).toBe(true)
        expect(/flex-wrap\s*:\s*wrap/i.test(style)).toBe(true)
        // All 2 fixture leaves under Total Revenue land in this one list.
        expect(revenueLeafList.querySelectorAll(':scope > li')).toHaveLength(2)
    })
})

// ── Spec requirement: confidence + opportunity-link preserved ───────────────

describe('EbitdaTree — preserved leaf-card affordances (spec requirement 5)', () => {
    it('renders an opportunity-link affordance on a leaf with linked_opportunity_indices', () => {
        // The leaf "subscriptions" has linked_opportunity_indices: [0]; OPPS
        // has one entry. The card surfaces the link via the shared
        // ``OpportunityDotStrip`` (testid preserved for compat with the
        // pre-extraction tests).
        render(<EbitdaTree treeData={FULL_TREE} opportunities={OPPS} />)
        const dotRow = screen.getByTestId('ebitda-linked-opportunity-dots')
        // The strip renders dots as aria-hidden <span> children of the
        // strip's outer wrapper; assert via that selector rather than
        // ``.children`` to avoid coupling to the strip's internal markup.
        const dots = dotRow.querySelectorAll('span[aria-hidden="true"]')
        expect(dots).toHaveLength(1)
        expect(dots[0].getAttribute('title')).toContain('Upsell premium tier')
    })

    it('does NOT render the legacy confidence chip on any leaf', () => {
        // Anti-regression for ``redesign-analysis-visuals`` P2: the
        // confidence chip was removed because Zack flagged it as
        // competing with the more decision-relevant opportunity dots.
        // ``confidence_level`` / ``confidence_basis`` data still flows
        // on every ``EbitdaNode`` but no chip should render.
        const tree: EbitdaNode[] = [
            {
                ...FULL_TREE[0],
                children: [
                    {
                        ...FULL_TREE[0].children![0],
                        confidence_level: 'medium',
                        confidence_basis: 'Partial signal.',
                    },
                ],
            },
            FULL_TREE[1],
            FULL_TREE[2],
            FULL_TREE[3],
            FULL_TREE[4],
        ]
        render(<EbitdaTree treeData={tree} opportunities={OPPS} />)
        expect(screen.queryByTestId('ebitda-confidence-chip')).toBeNull()
        // Also assert no ``Confidence: Medium`` accessible label is
        // present (legacy from the removed confidence-indicator visual
        // — guard against accidental regressions reintroducing it).
        expect(screen.queryByLabelText('Confidence: Medium')).toBeNull()
    })
})

// ── Empty / minimal tree handling ───────────────────────────────────────────

describe('EbitdaTree — minimal-data resilience', () => {
    it('handles an empty tree without crashing', () => {
        const { container } = render(<EbitdaTree treeData={[]} opportunities={[]} />)
        const waterfall = container.querySelector('[data-testid="ebitda-waterfall"]')
        expect(waterfall).not.toBeNull()
        expect(waterfall!.querySelectorAll(':scope > li')).toHaveLength(0)
    })
})
