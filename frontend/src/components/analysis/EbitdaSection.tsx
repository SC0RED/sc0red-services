'use client'

import dynamic from 'next/dynamic'

import HelpTooltip from '@/components/ui/HelpTooltip'
import type { EbitdaTree, Opportunity } from '@/lib/types/api'

const EbitdaTree = dynamic(() => import('@/components/EbitdaTree'), { ssr: false })

interface EbitdaSectionProps {
    ebitdaTree: EbitdaTree
    opportunities: Opportunity[]
}

export default function EbitdaSection({ ebitdaTree, opportunities }: EbitdaSectionProps) {
    return (
        <div style={{ marginBottom: '2rem' }}>
            <h2 className="section-header">
                EBITDA Impact Model
                <HelpTooltip term="ebitda_tree" />
            </h2>

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

            <div className="card" style={{ padding: '1rem' }}>
                <EbitdaTree treeData={ebitdaTree.treeData} opportunities={opportunities} />
            </div>
        </div>
    )
}
