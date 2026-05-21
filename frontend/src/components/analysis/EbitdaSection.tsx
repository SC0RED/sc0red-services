'use client'

import AnalysisLegend from '@/components/analysis/AnalysisLegend'
import EbitdaTree from '@/components/EbitdaTree'
import type { EbitdaNode, EbitdaTree as EbitdaTreeData, Opportunity } from '@/lib/types/api'

interface EbitdaSectionProps {
    ebitdaTree: EbitdaTreeData
    opportunities: Opportunity[]
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

/**
 * EBITDA Impact Model section wrapper.
 *
 * P2 of ``redesign-analysis-visuals`` removed the confidence chip from
 * leaf chips and the matching ``ebitda-confidence-legend`` caption that
 * sat above the tree — the chip competed with the more decision-
 * relevant opportunity-link dots. ``confidence_level`` /
 * ``confidence_basis`` data still flows on the API response for any
 * future surface (audit panel, debug overlay).
 *
 * The remaining legend is the shared ``AnalysisLegend`` component
 * (``tool="ebitda"``) — same copy + colour swatches the strategy map
 * and value chain use, ensuring cross-tool consistency.
 */
export default function EbitdaSection({ ebitdaTree, opportunities }: EbitdaSectionProps) {
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

            {showOpportunityLinkLegend && <AnalysisLegend tool="ebitda" />}

            <div className="card card--rich">
                <EbitdaTree treeData={ebitdaTree.treeData} opportunities={opportunities} />
            </div>
        </div>
    )
}
