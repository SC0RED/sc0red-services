'use client'

import EbitdaTree from '@/components/EbitdaTree'
import type { EbitdaNode, EbitdaTree as EbitdaTreeData, Opportunity } from '@/lib/types/api'
import { LEVER_COLORS } from '@/lib/utils/leverColors'

interface EbitdaSectionProps {
    ebitdaTree: EbitdaTreeData
    opportunities: Opportunity[]
}

/** Whether any leaf node in the tree carries a confidence level. We only
 *  surface the legend when at least one chip will actually render — older
 *  analyses (re-analyse or pre-this-feature) have no chips, so the legend
 *  would just confuse readers. */
function treeHasConfidence(nodes: EbitdaNode[]): boolean {
    for (const node of nodes) {
        if (
            node.confidence_level === 'high' ||
            node.confidence_level === 'medium' ||
            node.confidence_level === 'low'
        ) {
            return true
        }
        if (node.children && treeHasConfidence(node.children)) {
            return true
        }
    }
    return false
}

/** Whether any leaf in the tree carries a non-empty
 *  ``linked_opportunity_indices`` array. We gate the opportunity-link
 *  legend on this so older analyses without linked opportunities don't
 *  see an explanation for dots that aren't on the page. Walks the tree
 *  recursively — linked opportunities typically live on leaves but the
 *  predicate is permissive about depth. */
function treeHasLinkedOpportunities(nodes: EbitdaNode[]): boolean {
    for (const node of nodes) {
        if (node.linked_opportunity_indices && node.linked_opportunity_indices.length > 0) {
            return true
        }
        if (node.children && treeHasLinkedOpportunities(node.children)) {
            return true
        }
    }
    return false
}

export default function EbitdaSection({ ebitdaTree, opportunities }: EbitdaSectionProps) {
    const showConfidenceLegend = treeHasConfidence(ebitdaTree.treeData)
    const showOpportunityLinkLegend = treeHasLinkedOpportunities(ebitdaTree.treeData)
    return (
        <div className="analysis-section-spacing">
            {/* Section heading + help tooltip live at the page level via
                AnalysisSection (analysis-detail-consistency-wrapper D3). */}
            <div
                style={{
                    display: 'flex',
                    gap: '0.5rem',
                    flexWrap: 'wrap',
                    marginBottom: '1rem',
                }}
            >
                {ebitdaTree.revenueEstimate && (
                    <span className="badge badge-low">Revenue: {ebitdaTree.revenueEstimate}</span>
                )}
                {ebitdaTree.ebitdaEstimate && (
                    <span className="badge badge-blue">EBITDA: {ebitdaTree.ebitdaEstimate}</span>
                )}
            </div>

            {ebitdaTree.businessModelSummary && (
                <p
                    style={{
                        fontSize: '0.875rem',
                        lineHeight: 1.7,
                        color: 'var(--text-secondary)',
                        marginBottom: '1.25rem',
                    }}
                >
                    {ebitdaTree.businessModelSummary}
                </p>
            )}

            {showConfidenceLegend && (
                <div data-testid="ebitda-confidence-legend" style={legendStyle}>
                    <strong style={legendStrongStyle}>Confidence:</strong> derivation provenance, not
                    subjective quality. <strong style={legendStrongStyle}>High</strong> = both business model
                    and company size matched known templates.{' '}
                    <strong style={legendStrongStyle}>Medium</strong> = one input matched; the other
                    defaulted. <strong style={legendStrongStyle}>Low</strong> = both defaulted; figure is a
                    generic mid-market estimate.
                </div>
            )}

            {showOpportunityLinkLegend && (
                <div data-testid="ebitda-opportunity-link-legend" style={legendStyle}>
                    <strong style={legendStrongStyle}>Opportunity links:</strong>{' '}
                    <span aria-hidden="true" style={dotStyle(LEVER_COLORS['Revenue Side'])} />
                    <strong style={legendStrongStyle}>Revenue Side</strong> ·{' '}
                    <span aria-hidden="true" style={dotStyle(LEVER_COLORS['Cost Side'])} />
                    <strong style={legendStrongStyle}>Cost Side</strong> ·{' '}
                    <span aria-hidden="true" style={dotStyle(LEVER_COLORS.Both)} />
                    <strong style={legendStrongStyle}>Both</strong> — AI Opportunities targeting this P&amp;L
                    line.
                </div>
            )}

            <div className="card card--rich">
                <EbitdaTree treeData={ebitdaTree.treeData} opportunities={opportunities} />
            </div>
        </div>
    )
}

// ── legend styles ───────────────────────────────────────────────────────────

/** Shared by both the confidence legend and the opportunity-link
 *  legend — caption-step font, tertiary text color, low vertical
 *  rhythm. Each legend stacks as a separate row inside the section's
 *  header region. Co-managed so future styling changes hit both. */
const legendStyle: React.CSSProperties = {
    fontSize: '0.875rem',
    color: 'var(--text-tertiary)',
    marginBottom: '0.75rem',
    lineHeight: 1.6,
}

const legendStrongStyle: React.CSSProperties = {
    color: 'var(--text-secondary)',
}

/** Each legend dot is a 10 × 10 px inline-block circle filled with the
 *  matching ``--lever-*`` theme token. Slightly larger than the in-chip
 *  8 × 8 px dots so they read cleanly at legend typography scale —
 *  same trick the strategy-map ``ConfidenceLegend`` uses. */
function dotStyle(background: string): React.CSSProperties {
    return {
        display: 'inline-block',
        width: '10px',
        height: '10px',
        borderRadius: '50%',
        background,
        verticalAlign: 'middle',
        marginRight: '4px',
    }
}
