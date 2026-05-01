import type { OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

import PrintOpportunityCard from './PrintOpportunityCard'

interface PrintOpportunityListProps {
    /** Already-sorted opportunities; cards are grouped without re-sorting. */
    sortedOpportunities: OpportunityWithIndex[]
}

/**
 * AI Opportunity Roadmap section — one expanded card per opportunity,
 * grouped by `value_lever` (Revenue Side → Cost Side → Both → no
 * lever). Each group is preceded by a section divider naming the
 * lever; cards within a group keep their PDF-printed-index so cross-
 * section linkages (EBITDA, value chain) point at the correct card.
 *
 * Print-only counterpart to `OpportunitiesList`. The screen list shows
 * a category-filter chip row and collapse toggles per card; the print
 * version shows everything, no chrome.
 *
 * Returns null when there are no opportunities — the parent skips the
 * section break in that case so no empty page is produced.
 */
export default function PrintOpportunityList({ sortedOpportunities }: PrintOpportunityListProps) {
    if (!sortedOpportunities.length) return null

    const groups = groupByLever(sortedOpportunities)

    return (
        <section className="print-section print-section--break-before">
            <h2>AI Opportunity Roadmap</h2>
            {groups.map((group) => (
                <div key={group.lever ?? 'no-lever'} style={{ marginBottom: '24px' }}>
                    <LeverDivider lever={group.lever} />
                    <div
                        style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '14px',
                        }}
                    >
                        {group.entries.map((entry) => (
                            <PrintOpportunityCard
                                key={entry.printedIndex}
                                opportunity={entry.opportunity}
                                printedIndex={entry.printedIndex}
                            />
                        ))}
                    </div>
                </div>
            ))}
        </section>
    )
}

interface LeverGroup {
    lever: 'Revenue Side' | 'Cost Side' | 'Both' | null
    entries: OpportunityWithIndex[]
}

const LEVER_ORDER: Array<'Revenue Side' | 'Cost Side' | 'Both' | null> = [
    'Revenue Side',
    'Cost Side',
    'Both',
    null,
]

function groupByLever(entries: OpportunityWithIndex[]): LeverGroup[] {
    return LEVER_ORDER.map((lever) => ({
        lever,
        entries: entries.filter((entry) => (entry.opportunity.value_lever ?? null) === lever),
    })).filter((group) => group.entries.length > 0)
}

function LeverDivider({ lever }: { lever: LeverGroup['lever'] }) {
    const label = lever ?? 'Other'
    const color = lever ? (LEVER_COLORS[lever] ?? 'var(--text-secondary)') : 'var(--text-secondary)'
    return (
        <div
            data-print-lever-divider={label}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                margin: '0 0 12px',
            }}
        >
            <span
                style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    color,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    flexShrink: 0,
                }}
            >
                {label}
            </span>
            <span
                style={{
                    flex: 1,
                    height: '1px',
                    background: 'var(--border-subtle)',
                }}
            />
        </div>
    )
}
