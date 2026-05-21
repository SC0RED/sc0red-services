import { findByOriginalIndex, type OpportunityWithIndex } from '@/lib/pdf/sortOpportunities'
import type { EbitdaNode, EbitdaTree } from '@/lib/types/api'

interface PrintEbitdaOutlineProps {
    ebitdaTree: EbitdaTree
    /** Same sorted-with-original-index list used elsewhere in the PDF —
     * required so linkage callouts can resolve `linked_opportunity_indices`
     * to printed-index references. */
    sortedOpportunities: OpportunityWithIndex[]
}

/**
 * EBITDA Impact Model section — fully-expanded, static rendering as a
 * nested HTML outline (label → value range → percent → children,
 * indented). Replaces the interactive `EbitdaTree` (ReactFlow + dagre
 * + zoom/pan controls + "Scroll to pan…" help text) with a layout that
 * preserves parent-child hierarchy via indentation regardless of tree
 * shape.
 *
 * Earlier iterations tried a depth-bucketed CSS-grid rendering for
 * "small" trees, but real EBITDA trees are rarely balanced — a root
 * with one branch having three sub-branches and another with zero
 * collapses to a 3-column grid that looks structurally identical to a
 * tree where the root has three direct children. The outline form is
 * the right semantic for a printed document and tested cleanly against
 * the spec scenarios.
 *
 * Surfaces `linked_opportunity_indices` callouts per node, resolving
 * against the printed-PDF index of each opportunity card so the reader
 * can flip back from a tree branch to the relevant opportunity.
 *
 * The section keeps the `.print-ebitda` class — not for a named-page
 * override (the outline form fits A4 portrait cleanly; the legacy
 * `@page ebitda-page { size: A3 landscape; }` rule was removed when
 * the tree was retired) — but for the shared `page-break-inside:
 * avoid` selector in `print.css`.
 */

export default function PrintEbitdaOutline({ ebitdaTree, sortedOpportunities }: PrintEbitdaOutlineProps) {
    return (
        <section
            className="print-section print-section--break-before print-ebitda"
            data-render-mode="outline"
        >
            <h2>EBITDA Impact Model</h2>

            {ebitdaTree.businessModelSummary ? (
                <p
                    style={{
                        fontSize: '0.9rem',
                        lineHeight: 1.7,
                        color: 'var(--text-secondary)',
                        marginBottom: '20px',
                    }}
                >
                    {ebitdaTree.businessModelSummary}
                </p>
            ) : null}

            <div
                style={{
                    display: 'flex',
                    gap: '8px',
                    flexWrap: 'wrap',
                    marginBottom: '20px',
                }}
            >
                {ebitdaTree.revenueEstimate ? (
                    <span className="badge badge-low">Revenue: {ebitdaTree.revenueEstimate}</span>
                ) : null}
                {ebitdaTree.ebitdaEstimate ? (
                    <span className="badge badge-blue">EBITDA: {ebitdaTree.ebitdaEstimate}</span>
                ) : null}
            </div>

            <OutlineRender treeData={ebitdaTree.treeData} sortedOpportunities={sortedOpportunities} />
        </section>
    )
}

// ── Outline render ──────────────────────────────────────────────────

function OutlineRender({
    treeData,
    sortedOpportunities,
}: {
    treeData: EbitdaNode[]
    sortedOpportunities: OpportunityWithIndex[]
}) {
    return (
        <ol
            style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
            }}
        >
            {treeData.map((node) => (
                <OutlineNode key={node.id} node={node} sortedOpportunities={sortedOpportunities} />
            ))}
        </ol>
    )
}

function OutlineNode({
    node,
    sortedOpportunities,
}: {
    node: EbitdaNode
    sortedOpportunities: OpportunityWithIndex[]
}) {
    return (
        <li
            className="print-ebitda-outline-block"
            style={{
                paddingLeft: '12px',
                borderLeft: '2px solid var(--border-subtle)',
            }}
        >
            <EbitdaNodeCard node={node} sortedOpportunities={sortedOpportunities} />
            {node.children && node.children.length > 0 ? (
                <ol
                    style={{
                        listStyle: 'none',
                        margin: '8px 0 0',
                        padding: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                    }}
                >
                    {node.children.map((child) => (
                        <OutlineNode key={child.id} node={child} sortedOpportunities={sortedOpportunities} />
                    ))}
                </ol>
            ) : null}
        </li>
    )
}

// ── Node card ───────────────────────────────────────────────────────

interface EbitdaNodeCardProps {
    node: EbitdaNode
    sortedOpportunities: OpportunityWithIndex[]
}

function EbitdaNodeCard({ node, sortedOpportunities }: EbitdaNodeCardProps) {
    const links = (node.linked_opportunity_indices ?? [])
        .map((originalIndex) => findByOriginalIndex(sortedOpportunities, originalIndex))
        .filter((entry): entry is OpportunityWithIndex => entry != null)

    // The metadata row's bottom margin only applies when content
    // follows it (description paragraph or linkage callout). Computed
    // explicitly via `Boolean(...)` to keep nullish-coalescing
    // (`??`) the lone falsy operator in this file — the rest of the
    // codebase reaches for `??`, the previous `||` here was the only
    // outlier.
    const hasContentBelow = Boolean(node.description) || links.length > 0

    return (
        <div
            style={{
                padding: '10px 14px',
                background: 'var(--bg-surface-2)',
                border: '1px solid var(--border-subtle)',
                borderLeft: `3px solid ${typeColor(node.type)}`,
                borderRadius: '6px',
            }}
        >
            <div style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '4px' }}>{node.label}</div>
            <div
                style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '8px',
                    fontSize: '0.75rem',
                    color: 'var(--text-secondary)',
                    marginBottom: hasContentBelow ? '6px' : 0,
                }}
            >
                {node.value_range ? <span>{node.value_range}</span> : null}
                {typeof node.percentage_of_parent === 'number' ? (
                    // ``percentage_of_parent`` is emitted by the backend as
                    // an integer 0–100 (see
                    // ``backend/src/pipeline/pipeline_steps/build_ebitda_tree.py:64``
                    // ``_apply_percentage`` — the validator rejects any
                    // value outside that range). Don't multiply by 100;
                    // ``80`` already means "80% of parent". The web
                    // component at ``EbitdaNodeComponent.tsx`` renders it
                    // directly without multiplication; this print path was
                    // out of sync (introduced in PR #327, surfaced by the
                    // P2 architecture-reviewer pass).
                    <span>{Math.round(node.percentage_of_parent)}% of parent</span>
                ) : null}
                {/* Confidence level dropped from print parity with the
                    on-screen change (P2 of redesign-analysis-visuals).
                    The data still flows on EbitdaNode for future surfaces
                    but is no longer rendered here. */}
            </div>
            {node.description ? (
                <p
                    style={{
                        fontSize: '0.8rem',
                        lineHeight: 1.6,
                        color: 'var(--text-primary)',
                        margin: '0 0 6px',
                    }}
                >
                    {node.description}
                </p>
            ) : null}
            {links.length > 0 ? (
                <div
                    style={{
                        fontSize: '0.7rem',
                        color: 'var(--accent-blue)',
                        lineHeight: 1.5,
                    }}
                >
                    Opportunities:{' '}
                    {links.map((link, idx) => (
                        <span key={link.printedIndex}>
                            #{link.printedIndex} ({link.opportunity.title})
                            {idx < links.length - 1 ? ', ' : ''}
                        </span>
                    ))}
                </div>
            ) : null}
        </div>
    )
}

function typeColor(type: EbitdaNode['type']): string {
    switch (type) {
        case 'revenue':
            return 'var(--risk-low)'
        case 'cost':
            return 'var(--risk-high)'
        case 'margin':
            return 'var(--accent-blue)'
        case 'subtotal':
        default:
            return 'var(--text-secondary)'
    }
}
