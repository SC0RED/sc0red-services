'use client'

import EbitdaTree from '@/components/EbitdaTree'
import type { EbitdaNode, EbitdaTree as EbitdaTreeData, Opportunity } from '@/lib/types/api'

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

export default function EbitdaSection({ ebitdaTree, opportunities }: EbitdaSectionProps) {
    const showConfidenceLegend = treeHasConfidence(ebitdaTree.treeData)
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
                        fontSize: '0.9rem',
                        lineHeight: 1.7,
                        color: 'var(--text-secondary)',
                        marginBottom: '1.25rem',
                    }}
                >
                    {ebitdaTree.businessModelSummary}
                </p>
            )}

            {showConfidenceLegend && (
                <div
                    data-testid="ebitda-confidence-legend"
                    style={{
                        fontSize: '0.8125rem',
                        color: 'var(--text-tertiary)',
                        marginBottom: '0.75rem',
                        lineHeight: 1.6,
                    }}
                >
                    <strong style={{ color: 'var(--text-secondary)' }}>Confidence:</strong> derivation
                    provenance, not subjective quality.{' '}
                    <strong style={{ color: 'var(--text-secondary)' }}>High</strong> = both business model and
                    company size matched known templates.{' '}
                    <strong style={{ color: 'var(--text-secondary)' }}>Medium</strong> = one input matched;
                    the other defaulted. <strong style={{ color: 'var(--text-secondary)' }}>Low</strong> =
                    both defaulted; figure is a generic mid-market estimate.
                </div>
            )}

            <div className="card card--rich">
                <EbitdaTree treeData={ebitdaTree.treeData} opportunities={opportunities} />
            </div>
        </div>
    )
}
