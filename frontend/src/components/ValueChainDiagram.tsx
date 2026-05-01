'use client'

import { useState } from 'react'

import type { ValueChainStep, Opportunity } from '@/lib/types/api'
import { CAT_LABELS, RISK_CATEGORY_COLORS } from '@/lib/utils/riskUtils'

interface ValueChainDiagramProps {
    steps: ValueChainStep[]
    opportunities: Opportunity[]
    summary: string
}

export default function ValueChainDiagram({ steps, opportunities, summary }: ValueChainDiagramProps) {
    const [expandedStep, setExpandedStep] = useState<string | null>(null)

    const primarySteps = steps.filter((s) => s.category === 'primary')
    const supportSteps = steps.filter((s) => s.category === 'support')

    return (
        <div style={{ marginBottom: '2rem' }}>
            <h2 className="section-header">Value Chain Analysis</h2>

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
                        isExpanded={expandedStep === step.id}
                        onToggle={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
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
                                isExpanded={expandedStep === step.id}
                                onToggle={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
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
    isExpanded: boolean
    onToggle: () => void
}

function StepCard({ step, opportunities, variant, isLast, isExpanded, onToggle }: StepCardProps) {
    const linkedOpportunities = step.opportunity_indices
        .filter((i) => i >= 0 && i < opportunities.length)
        .map((i) => ({ index: i, opportunity: opportunities[i] }))
    const isPrimary = variant === 'primary'

    return (
        <div
            style={{
                display: 'flex',
                alignItems: 'stretch',
                flex: '1 1 0',
                minWidth: isPrimary ? '140px' : '160px',
            }}
        >
            <button
                onClick={onToggle}
                aria-expanded={isExpanded}
                className="card"
                style={{
                    flex: 1,
                    padding: '0.875rem',
                    cursor: 'pointer',
                    background: 'none',
                    borderTop: `1px solid ${isExpanded ? 'var(--accent-blue)' : 'var(--border)'}`,
                    borderBottom: `1px solid ${isExpanded ? 'var(--accent-blue)' : 'var(--border)'}`,
                    borderLeft: `1px solid ${isExpanded ? 'var(--accent-blue)' : 'var(--border)'}`,
                    borderRight:
                        isPrimary && !isLast
                            ? 'none'
                            : `1px solid ${isExpanded ? 'var(--accent-blue)' : 'var(--border)'}`,
                    borderRadius: isPrimary && !isLast ? '0' : undefined,
                    textAlign: 'left',
                    transition: 'border-color 0.2s, background 0.2s',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.5rem',
                }}
            >
                {/* Label */}
                <div
                    style={{
                        fontWeight: 600,
                        fontSize: '0.8125rem',
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
                                fontSize: '0.625rem',
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

                {/* Opportunity count */}
                {linkedOpportunities.length > 0 && (
                    <div
                        style={{
                            fontSize: '0.6875rem',
                            color: 'var(--accent-blue)',
                            fontWeight: 500,
                        }}
                    >
                        {linkedOpportunities.length} opportunit
                        {linkedOpportunities.length === 1 ? 'y' : 'ies'}
                    </div>
                )}

                {/* Expanded detail */}
                {isExpanded && linkedOpportunities.length > 0 && (
                    <div
                        style={{
                            borderTop: '1px solid var(--border)',
                            paddingTop: '0.5rem',
                            marginTop: '0.25rem',
                        }}
                    >
                        <div
                            style={{
                                fontSize: '0.6875rem',
                                fontWeight: 600,
                                color: 'var(--text-tertiary)',
                                marginBottom: '0.375rem',
                                textTransform: 'uppercase',
                                letterSpacing: '0.04em',
                            }}
                        >
                            Linked Opportunities
                        </div>
                        {linkedOpportunities.map(({ index, opportunity }) => (
                            <div
                                key={index}
                                style={{
                                    fontSize: '0.75rem',
                                    color: 'var(--text-primary)',
                                    padding: '0.25rem 0',
                                    lineHeight: 1.4,
                                }}
                            >
                                {opportunity.title}
                            </div>
                        ))}
                    </div>
                )}
            </button>

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
