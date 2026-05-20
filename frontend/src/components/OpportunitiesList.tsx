'use client'

import { useEffect, useRef, useState } from 'react'

import ExpandableCard from '@/components/ui/ExpandableCard'
import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import { LEVER_COLORS } from '@/lib/utils/leverColors'
import type { Opportunity } from '@/lib/types/api'

function ImpactBadge({ impact }: { impact: string }) {
    const colorMap: Record<string, string> = { High: 'low', Medium: 'moderate', Low: 'neutral' }
    return <span className={`badge badge-${colorMap[impact] || 'neutral'}`}>{impact} Impact</span>
}

function TimelineBadge({ timeline }: { timeline: string }) {
    return (
        <span className="badge badge-blue" style={{ fontSize: '0.75rem' }}>
            {timeline}
        </span>
    )
}

interface OpportunitiesListProps {
    opportunities: Opportunity[]
    activeLever: string
}

/**
 * AI Opportunities list. The CTA banner that previously lived at the
 * bottom of this component was removed as part of the
 * improve-pdf-export-content change — the print PDF was rendering it
 * twice (once here, once on the back cover), and the cleanest fix is
 * to host the CTA at the parent surface (the analysis detail page)
 * rather than per-list. Print path uses `PrintBackCover` instead.
 */
export default function OpportunitiesList({ opportunities, activeLever }: OpportunitiesListProps) {
    const [activeOppCat, setActiveOppCat] = useState<string>('All')
    const [expandedOpp, setExpandedOpp] = useState<string | null>(null)

    const uniqueCategories = opportunities
        .map((o) => o.strategic_category)
        .filter((cat, index, arr) => arr.indexOf(cat) === index)
    const oppCategories = ['All', ...uniqueCategories]
    // Pair each opportunity with its ORIGINAL index in the API array
    // BEFORE filtering. The P5 hover-provider keys highlight state on
    // original indices (the same indices ``linked_opportunity_indices``
    // points at), so a filtered view that lost the mapping would
    // silently fail to highlight matching cards.
    const filteredOpps = opportunities
        .map((opp, originalIndex) => ({ opp, originalIndex }))
        .filter(({ opp }) => {
            if (activeOppCat !== 'All' && opp.strategic_category !== activeOppCat) return false
            if (activeLever !== 'All' && opp.value_lever !== activeLever) return false
            return true
        })

    return (
        <div className="analysis-section-spacing">
            {/* Section heading + count badge live at the page level via
                AnalysisSection (analysis-detail-consistency-wrapper D2 +
                D3). The category-chip filter strip stays here as a body
                control, rendered as its own row above the opportunity
                cards. */}
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'flex-start',
                    alignItems: 'center',
                    marginBottom: '1rem',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                }}
            >
                {oppCategories.map((cat) => (
                    <button
                        key={cat}
                        onClick={() => setActiveOppCat(cat)}
                        style={{
                            padding: '0.3rem 0.75rem',
                            borderRadius: 'var(--radius-full)',
                            border: '1px solid',
                            borderColor: activeOppCat === cat ? 'var(--accent-blue)' : 'var(--border)',
                            background: activeOppCat === cat ? 'rgba(59,123,246,0.1)' : 'transparent',
                            color: activeOppCat === cat ? 'var(--accent-blue)' : 'var(--text-secondary)',
                            fontSize: '0.75rem',
                            fontWeight: 500,
                            cursor: 'pointer',
                            transition: 'all var(--transition-fast)',
                        }}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
                {filteredOpps.map(({ opp, originalIndex }) => {
                    const isOpen = expandedOpp === opp.title
                    return (
                        <HoverableOpportunityCard key={opp.title} originalIndex={originalIndex}>
                            <ExpandableCard
                                id={opp.title}
                                isOpen={isOpen}
                                onToggle={() => setExpandedOpp(isOpen ? null : opp.title)}
                                header={<OpportunityHeader opp={opp} />}
                            >
                                <OpportunityBody opp={opp} />
                            </ExpandableCard>
                        </HoverableOpportunityCard>
                    )
                })}
            </div>
        </div>
    )
}

/**
 * Wraps each opportunity card with the P5 hover-provider integration.
 *
 * - SOURCE: hovering / focusing the card calls
 *   ``highlightOpportunities([originalIndex])`` so sources elsewhere
 *   (EBITDA leaves, value-chain steps) that reference this opportunity
 *   can react to the reverse-direction lookup.
 * - TARGET: when the provider's ``hoveredOpportunityIndices`` includes
 *   this card's ``originalIndex``, the wrapper applies the
 *   ``.card-pulse`` class (one-shot 400 ms outline glow) and calls
 *   ``scrollIntoView({ block: 'nearest' })`` so the card lands in the
 *   viewport if it was scrolled offscreen. ``nearest`` means we only
 *   scroll when the card is fully out of view — already-visible cards
 *   stay put.
 *
 * Stateless about its own pulse: the class is toggled by re-running
 * the component each time ``isHovered`` flips. Re-applying the class
 * restarts the animation because browsers reset CSS animations when
 * a class carrying an ``animation`` shorthand is removed and re-added
 * to the same element. React's reconciler keeps the DOM node stable
 * (no remount) — the animation restart is a browser-level side-effect
 * of the class toggle, not a React lifecycle event.
 */
function HoverableOpportunityCard({
    originalIndex,
    children,
}: {
    originalIndex: number
    children: React.ReactNode
}) {
    const { hoveredOpportunityIndices, highlightOpportunities, clearHighlight } = useOpportunityHover()
    const isHovered = hoveredOpportunityIndices.includes(originalIndex)
    const wasHovered = useRef(false)
    const wrapperRef = useRef<HTMLDivElement>(null)

    // On transition INTO highlight state, scroll the card into view.
    // ``block: 'nearest'`` means already-visible cards don't move;
    // only offscreen cards scroll. We compare against the previous
    // ``isHovered`` (via ref) so we don't re-scroll on every render
    // while the card stays hovered.
    useEffect(() => {
        if (isHovered && !wasHovered.current) {
            wrapperRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        }
        wasHovered.current = isHovered
    }, [isHovered])

    // ``onBlur`` bubbles up from any focusable descendant — including
    // the ``<button>`` inside ``ExpandableCard``. A naive
    // ``onBlur={clearHighlight}`` would fire when keyboard focus
    // moves FROM the wrapper INTO the expand button, clearing the
    // highlight that ``onFocus`` had just set. Guard against bubbling
    // by checking whether focus moved to a descendant.
    function handleBlur(event: React.FocusEvent<HTMLDivElement>) {
        const next = event.relatedTarget as Node | null
        if (event.currentTarget.contains(next)) return
        clearHighlight()
    }

    return (
        <div
            ref={wrapperRef}
            data-testid={`opportunity-card-${originalIndex}`}
            className={isHovered ? 'card-pulse' : undefined}
            onMouseEnter={() => highlightOpportunities([originalIndex])}
            onMouseLeave={clearHighlight}
            onFocus={() => highlightOpportunities([originalIndex])}
            onBlur={handleBlur}
        >
            {children}
        </div>
    )
}

/**
 * Header content for an opportunity's ExpandableCard. Title +
 * impact/timeline/category/value-lever badge cluster. Lives next
 * to the chevron in the expandable-card trigger row.
 */
function OpportunityHeader({ opp }: { opp: Opportunity }) {
    return (
        <div style={{ flex: 1 }}>
            <div
                style={{
                    fontWeight: 700,
                    fontSize: '1rem',
                    marginBottom: '0.5rem',
                }}
            >
                {opp.title}
            </div>
            <div
                style={{
                    display: 'flex',
                    gap: '0.5rem',
                    flexWrap: 'wrap',
                }}
            >
                <ImpactBadge impact={opp.impact_rating} />
                <TimelineBadge timeline={opp.timeline} />
                <span className="badge badge-neutral">{opp.strategic_category}</span>
                {opp.value_lever && (
                    <span
                        style={{
                            padding: '0.15rem 0.5rem',
                            borderRadius: 'var(--radius-full)',
                            fontSize: '0.75rem',
                            fontWeight: 500,
                            border: '1px solid',
                            borderColor: LEVER_COLORS[opp.value_lever] || 'var(--text-secondary)',
                            color: LEVER_COLORS[opp.value_lever] || 'var(--text-secondary)',
                        }}
                    >
                        {opp.value_lever}
                    </span>
                )}
            </div>
        </div>
    )
}

/**
 * Body content for an opportunity's ExpandableCard. Description +
 * implementation steps + investment + ROI grid.
 */
function OpportunityBody({ opp }: { opp: Opportunity }) {
    return (
        <>
            <p
                style={{
                    fontSize: '0.875rem',
                    lineHeight: 1.75,
                    color: 'var(--text-primary)',
                    marginTop: 0,
                    marginBottom: '1.5rem',
                    whiteSpace: 'pre-line',
                }}
            >
                {opp.description}
            </p>

            {opp.implementation_steps && opp.implementation_steps.length > 0 && (
                <div style={{ marginBottom: '1.25rem' }}>
                    <div
                        style={{
                            fontWeight: 600,
                            fontSize: '0.875rem',
                            color: 'var(--text-secondary)',
                            marginBottom: '0.75rem',
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                        }}
                    >
                        Implementation Steps
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {opp.implementation_steps.map((step, si) => (
                            <div
                                key={si}
                                style={{
                                    display: 'flex',
                                    gap: '0.75rem',
                                    alignItems: 'flex-start',
                                }}
                            >
                                <span
                                    style={{
                                        minWidth: '22px',
                                        height: '22px',
                                        borderRadius: '50%',
                                        background: 'rgba(59,123,246,0.12)',
                                        color: 'var(--accent-blue)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: '0.75rem',
                                        fontWeight: 700,
                                        flexShrink: 0,
                                        marginTop: '2px',
                                    }}
                                >
                                    {si + 1}
                                </span>
                                <p style={{ fontSize: '0.875rem', lineHeight: 1.6, margin: 0 }}>{step}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '0.875rem',
                }}
            >
                <div
                    style={{
                        padding: '1rem',
                        background: 'var(--bg-surface-3)',
                        borderRadius: 'var(--radius-md)',
                        borderLeft: '3px solid var(--risk-moderate)',
                    }}
                >
                    <div
                        style={{
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            color: 'var(--text-tertiary)',
                            marginBottom: '0.375rem',
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                        }}
                    >
                        Estimated Investment
                    </div>
                    <div style={{ fontWeight: 700, color: 'var(--risk-moderate)' }}>
                        {opp.investment_range}
                    </div>
                </div>
                <div
                    style={{
                        padding: '1rem',
                        background: 'var(--bg-surface-3)',
                        borderRadius: 'var(--radius-md)',
                        borderLeft: '3px solid var(--risk-low)',
                    }}
                >
                    <div
                        style={{
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            color: 'var(--text-tertiary)',
                            marginBottom: '0.375rem',
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                        }}
                    >
                        Potential ROI
                    </div>
                    <div style={{ fontWeight: 600, color: 'var(--risk-low)', fontSize: '0.875rem' }}>
                        {opp.roi_estimate}
                    </div>
                </div>
            </div>
        </>
    )
}
