'use client'

import AnalysisLegend from '@/components/analysis/AnalysisLegend'
import OpportunityDotStrip from '@/components/analysis/OpportunityDotStrip'
import SourceLinkedOpportunitiesPopover from '@/components/analysis/SourceLinkedOpportunitiesPopover'
import { useOpportunityHover } from '@/lib/hooks/useOpportunityHover'
import type { ValueChainStep, Opportunity } from '@/lib/types/api'
import { CAT_LABELS, RISK_CATEGORY_COLORS } from '@/lib/utils/riskUtils'

interface ValueChainDiagramProps {
    steps: ValueChainStep[]
    opportunities: Opportunity[]
    summary: string
}

/**
 * Porter-style value chain renderer.
 *
 * Each step is a static card carrying the step label, a one-line
 * description, the risk-category tags, and a shared
 * ``OpportunityDotStrip`` showing the linked opportunities (one
 * coloured dot per linked ``opportunity_indices`` entry; colour from
 * ``LEVER_COLORS`` keyed on the opportunity's ``value_lever``).
 *
 * The previous click-to-expand interaction that surfaced a text list
 * of linked opportunity titles was removed by P4 of
 * ``redesign-analysis-visuals``. The dot strip carries the same
 * "this step has N opportunities" signal more compactly, and each
 * dot's native ``title`` attribute surfaces the opportunity name on
 * hover. The Phase-5 hover provider will further wire dot hover →
 * highlight matching opportunity card below; the diagram is hover-
 * provider-ready by virtue of using the shared strip component.
 */
export default function ValueChainDiagram({ steps, opportunities, summary }: ValueChainDiagramProps) {
    const primarySteps = steps.filter((s) => s.category === 'primary')
    const supportSteps = steps.filter((s) => s.category === 'support')

    // Show the shared legend only when at least one step would actually
    // render a visible dot — i.e. some step has an in-range opportunity
    // index that resolves to an entry in ``opportunities``. Gating
    // purely on ``opportunity_indices.length > 0`` would leave the
    // legend stranded above an empty strip if ``opportunities=[]``
    // (e.g. a stale analysis where opportunities were cleared but the
    // value-chain step indices weren't).
    const showLegend = steps.some((step) =>
        (step.opportunity_indices ?? []).some((index) => index >= 0 && index < opportunities.length)
    )

    return (
        <div className="analysis-section-spacing">
            {/* Section heading lives at the page level via AnalysisSection
                (analysis-detail-consistency-wrapper D3). */}
            <p
                style={{
                    fontSize: '0.875rem',
                    color: 'var(--text-secondary)',
                    lineHeight: 1.6,
                    marginBottom: '1.25rem',
                }}
            >
                {summary}
            </p>

            {showLegend && <AnalysisLegend tool="value-chain" />}

            {/* Primary Activities */}
            <div
                style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'var(--text-tertiary)',
                    marginBottom: '0.5rem',
                }}
            >
                Primary Activities
            </div>
            <div
                data-testid="primary-activities"
                style={{
                    display: 'flex',
                    gap: 0,
                    marginBottom: '1rem',
                    overflow: 'auto',
                }}
            >
                {primarySteps.map((step, index) => (
                    <StepCard
                        key={step.id}
                        step={step}
                        opportunities={opportunities}
                        variant="primary"
                        isLast={index === primarySteps.length - 1}
                    />
                ))}
            </div>

            {/* Support Activities */}
            {supportSteps.length > 0 && (
                <>
                    <div
                        style={{
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.06em',
                            color: 'var(--text-tertiary)',
                            marginBottom: '0.5rem',
                        }}
                    >
                        Support Activities
                    </div>
                    <div
                        data-testid="support-activities"
                        style={{
                            display: 'flex',
                            gap: '0.625rem',
                            overflow: 'auto',
                        }}
                    >
                        {supportSteps.map((step) => (
                            <StepCard
                                key={step.id}
                                step={step}
                                opportunities={opportunities}
                                variant="support"
                                isLast={true}
                            />
                        ))}
                    </div>
                </>
            )}
        </div>
    )
}

// ── Step Card ────────────────────────────────────────────────────

interface StepCardProps {
    step: ValueChainStep
    opportunities: Opportunity[]
    variant: 'primary' | 'support'
    isLast: boolean
}

function StepCard({ step, opportunities, variant, isLast }: StepCardProps) {
    const isPrimary = variant === 'primary'
    const indices = step.opportunity_indices ?? []
    // P5 hover-provider wiring: hovering / focusing the card publishes
    // the step's ``opportunity_indices`` so OpportunitiesList cards
    // below pulse. ``useOpportunityHover`` returns a no-op outside
    // the provider so isolated component tests stay harmless.
    const { highlightOpportunities, clearHighlight } = useOpportunityHover()
    const hasLinks = indices.length > 0
    const onEnter = () => {
        if (hasLinks) highlightOpportunities(indices)
    }
    // ``onBlur`` bubbles from focusable descendants (the dot strip's
    // overflow ``+N`` badge has ``tabIndex={0}``). Guard against the
    // bubble so tabbing into a descendant doesn't clear the highlight
    // ``onFocus`` had just set.
    const onBlur = (event: React.FocusEvent<HTMLElement>) => {
        // Loosened from ``HTMLDivElement`` to ``HTMLElement`` so the
        // handler matches the ``SourceLinkedOpportunitiesPopover``
        // ``sourceProps.onBlur`` signature. The runtime behaviour is
        // unchanged — the popover wrapper is still a ``<div>``.
        const next = event.relatedTarget as Node | null
        if (event.currentTarget.contains(next)) return
        clearHighlight()
    }

    // Phase 13: wrap the inner ``.card`` div in
    // ``SourceLinkedOpportunitiesPopover`` so hovering / focusing
    // surfaces an inline popover listing the linked opportunity
    // titles. The wrapper carries the tabIndex + hover handlers; the
    // inner content is purely visual. Empty-linkage steps render the
    // wrapper but the popover short-circuits internally.
    const cardStyle = {
        flex: 1,
        padding: '0.875rem',
        background: 'none',
        borderTop: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
        borderLeft: '1px solid var(--border)',
        borderRight: isPrimary && !isLast ? 'none' : '1px solid var(--border)',
        borderRadius: isPrimary && !isLast ? '0' : undefined,
        textAlign: 'left' as const,
        display: 'flex' as const,
        flexDirection: 'column' as const,
        gap: '0.5rem',
    }

    return (
        <div
            data-testid={`value-chain-step-${step.id}`}
            style={{
                display: 'flex',
                alignItems: 'stretch',
                flex: '1 1 0',
                minWidth: isPrimary ? '140px' : '160px',
            }}
        >
            <SourceLinkedOpportunitiesPopover
                anchorId={`value-chain-step-${step.id}`}
                linkedIndices={indices}
                opportunities={opportunities}
                sourceProps={{
                    tabIndex: 0,
                    onMouseEnter: onEnter,
                    onMouseLeave: clearHighlight,
                    onFocus: onEnter,
                    onBlur,
                    className: 'card',
                    style: cardStyle,
                }}
            >
                {/* Label */}
                <div
                    style={{
                        fontWeight: 600,
                        fontSize: '0.875rem',
                        color: 'var(--text-primary)',
                        lineHeight: 1.3,
                    }}
                >
                    {step.label}
                </div>

                {/* Description */}
                <div
                    style={{
                        fontSize: '0.75rem',
                        color: 'var(--text-secondary)',
                        lineHeight: 1.5,
                    }}
                >
                    {step.description}
                </div>

                {/* Risk tags */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem', marginTop: 'auto' }}>
                    {step.risk_categories.map((category) => (
                        <span
                            key={category}
                            style={{
                                fontSize: '0.75rem',
                                fontWeight: 500,
                                padding: '0.125rem 0.375rem',
                                borderRadius: '9999px',
                                background: `${RISK_CATEGORY_COLORS[category] ?? 'var(--text-tertiary)'}15`,
                                color: RISK_CATEGORY_COLORS[category] ?? 'var(--text-tertiary)',
                                border: `1px solid ${RISK_CATEGORY_COLORS[category] ?? 'var(--text-tertiary)'}30`,
                                whiteSpace: 'nowrap',
                            }}
                        >
                            {CAT_LABELS[category] ?? category}
                        </span>
                    ))}
                </div>

                {/* Opportunity-link dot strip — same shared component as
                    EBITDA leaves (and Phase 6 strategy-map cells). */}
                <OpportunityDotStrip
                    linkedIndices={indices}
                    opportunities={opportunities}
                    testId={`value-chain-linked-opportunity-dots-${step.id}`}
                />
            </SourceLinkedOpportunitiesPopover>

            {/* Arrow between primary steps */}
            {isPrimary && !isLast && (
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        color: 'var(--text-tertiary)',
                        fontSize: '1rem',
                    }}
                >
                    <svg width="8" height="16" viewBox="0 0 8 16" fill="none">
                        <path d="M1 1L7 8L1 15" stroke="var(--border)" strokeWidth="1.5" />
                    </svg>
                </div>
            )}
        </div>
    )
}
