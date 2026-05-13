'use client'

import type { CSSProperties } from 'react'

import EbitdaNodeComponent, { type EbitdaCardProps } from '@/components/EbitdaNodeComponent'
import type { EbitdaNode } from '@/lib/types/api'

/**
 * Static vertical-waterfall renderer for the EBITDA Impact Model.
 *
 * The five top-level rollups (Total Revenue, Cost of Revenue, Gross
 * Profit, Operating Expenses, EBITDA) appear top-to-bottom in P&L
 * order. Between each adjacent pair sits a "minus" or "equals"
 * connector that names the arithmetic relationship. Each subtotal's
 * leaves render to the right of the parent card on viewports
 * ≥ 768 px and stack below the parent on viewports < 768 px (driven
 * entirely by ``flex-wrap``; no JS-driven layout).
 *
 * This replaces a React Flow + dagre canvas (pan/zoom/fit affordances)
 * that consistently rendered too small to read by default. The new
 * layout is sized to the content; there is nothing to fit and
 * nothing to expand. See ``openspec/changes/redesign-ebitda-impact-model/``
 * for the design.
 */

/** Connector labels between adjacent subtotals. The backend emits the
 *  five subtotals in P&L order, so the four connectors are always
 *  ``[minus, equals, minus, equals]``:
 *
 *    Total Revenue  ── minus  →  Cost of Revenue
 *    Cost of Revenue ── equals →  Gross Profit
 *    Gross Profit   ── minus  →  Operating Expenses
 *    Operating Expns ── equals →  EBITDA
 */
const CONNECTOR_LABELS: ReadonlyArray<'minus' | 'equals'> = ['minus', 'equals', 'minus', 'equals']

/** Kebab-case identifier slug for an ``aria-labelledby`` reference and
 *  a CSS class targeted by leaf-area styles. */
const WATERFALL_HEADING_ID = 'ebitda-waterfall-heading'

interface EbitdaTreeProps {
    treeData: EbitdaNode[]
    opportunities: Array<{ title: string; value_lever?: string }>
}

export default function EbitdaTree({ treeData, opportunities }: EbitdaTreeProps) {
    return (
        <section data-testid="ebitda-tree" aria-labelledby={WATERFALL_HEADING_ID} style={sectionStyle}>
            {/* Visually-hidden heading anchors the section's accessible
                name. The on-page heading lives at the AnalysisSection
                wrapper level per analysis-detail-consistency-wrapper D3. */}
            <h2 id={WATERFALL_HEADING_ID} style={visuallyHiddenStyle}>
                EBITDA Impact Model
            </h2>
            <ol data-testid="ebitda-waterfall" style={waterfallStyle}>
                {treeData.map((subtotal, index) => (
                    <SubtotalRow
                        key={subtotal.id}
                        subtotal={subtotal}
                        opportunities={opportunities}
                        connectorBelow={resolveConnectorBelow(index, treeData.length)}
                    />
                ))}
            </ol>
        </section>
    )
}

function SubtotalRow({
    subtotal,
    opportunities,
    connectorBelow,
}: {
    subtotal: EbitdaNode
    opportunities: EbitdaTreeProps['opportunities']
    connectorBelow: 'minus' | 'equals' | null
}) {
    const leaves = subtotal.children ?? []
    return (
        <li style={subtotalRowItemStyle}>
            <div style={subtotalRowContentStyle}>
                <div style={parentCardWrapperStyle}>
                    <EbitdaNodeComponent {...nodeToCardProps(subtotal, opportunities)} isSubtotalHeading />
                </div>
                {leaves.length > 0 && (
                    <ul aria-label={`Drivers of ${subtotal.label}`} style={leafListStyle}>
                        {leaves.map((leaf) => (
                            <li key={leaf.id} style={leafListItemStyle}>
                                <EbitdaNodeComponent {...nodeToCardProps(leaf, opportunities)} />
                            </li>
                        ))}
                    </ul>
                )}
            </div>
            {connectorBelow && <Connector label={connectorBelow} />}
        </li>
    )
}

function Connector({ label }: { label: 'minus' | 'equals' }) {
    return (
        <div
            data-testid={`ebitda-connector-${label}`}
            style={connectorStyle}
            aria-label={label === 'minus' ? 'minus' : 'equals'}
        >
            <span aria-hidden="true" style={connectorArrowStyle}>
                ▼
            </span>
            <span style={connectorLabelStyle}>{label}</span>
        </div>
    )
}

/** Resolve the connector label that renders below the subtotal at
 *  ``index`` within a waterfall of ``length`` subtotals.
 *
 *  Returns ``null`` for the final subtotal (no connector below it).
 *  Returns ``null`` when the index walks past the canonical
 *  ``CONNECTOR_LABELS`` table — a backend producing more than the
 *  expected five subtotals would otherwise silently render undefined
 *  labels. We render nothing in that case rather than guessing the
 *  arithmetic; a fail-loud assertion would be too aggressive for what
 *  is presentational output.
 */
function resolveConnectorBelow(index: number, length: number): 'minus' | 'equals' | null {
    if (index >= length - 1) return null
    return CONNECTOR_LABELS[index] ?? null
}

/** Map an ``EbitdaNode`` (backend shape with snake_case fields) to the
 *  ``EbitdaCardProps`` (camelCase) the card component consumes. */
function nodeToCardProps(node: EbitdaNode, opportunities: EbitdaTreeProps['opportunities']): EbitdaCardProps {
    return {
        label: node.label,
        type: node.type,
        valueRange: node.value_range,
        percentageOfParent: node.percentage_of_parent,
        // ``description`` is a required string on ``EbitdaNode``; missing
        // values are a schema bug, not a render-time fallback case. The
        // card itself already skips rendering the hover tooltip when the
        // string is empty.
        description: node.description,
        // ``linked_opportunity_indices`` is required on ``EbitdaNode``
        // but legacy records persisted before the field was added carry
        // ``undefined``. Keep the ``?? []`` as forward-compat for those
        // records — without it the next ``.filter`` would throw.
        linkedOpportunities: (node.linked_opportunity_indices ?? [])
            .filter((i) => i >= 0 && i < opportunities.length)
            .map((i) => ({
                title: opportunities[i].title,
                valueLever: opportunities[i].value_lever ?? '',
            })),
        confidenceLevel: node.confidence_level,
        confidenceBasis: node.confidence_basis,
    }
}

// ── styles ──────────────────────────────────────────────────────────────────

const sectionStyle: CSSProperties = {
    display: 'block',
    width: '100%',
}

const visuallyHiddenStyle: CSSProperties = {
    position: 'absolute',
    width: 1,
    height: 1,
    padding: 0,
    margin: -1,
    overflow: 'hidden',
    clip: 'rect(0,0,0,0)',
    whiteSpace: 'nowrap',
    border: 0,
}

const waterfallStyle: CSSProperties = {
    listStyle: 'none',
    padding: 0,
    margin: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: 0,
}

const subtotalRowItemStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    width: '100%',
}

/** Parent card on the left, leaves wrap to the right (desktop) or
 *  below (mobile). The flex container itself stays centered in the
 *  column so subtotals with no leaves (Gross Profit, EBITDA) sit
 *  centered while subtotals with leaves push their leaves outward.
 *
 *  ``alignItems: 'flex-start'`` keeps the parent card aligned to the
 *  top of the leaf stack when the leaf list is taller than the parent. */
const subtotalRowContentStyle: CSSProperties = {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'flex-start',
    justifyContent: 'center',
    gap: '20px',
    width: '100%',
}

const parentCardWrapperStyle: CSSProperties = {
    flex: '0 0 auto',
    minWidth: '240px',
    maxWidth: '320px',
}

const leafListStyle: CSSProperties = {
    listStyle: 'none',
    padding: 0,
    margin: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    flex: '1 1 280px',
    maxWidth: '420px',
    minWidth: '240px',
}

const leafListItemStyle: CSSProperties = {
    display: 'block',
}

const connectorStyle: CSSProperties = {
    display: 'inline-flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '2px',
    margin: '14px 0',
    color: 'var(--text-tertiary)',
    fontSize: '0.75rem',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    fontWeight: 600,
    alignSelf: 'center',
}

const connectorArrowStyle: CSSProperties = {
    color: 'var(--text-secondary)',
    fontSize: '0.85rem',
    lineHeight: 1,
}

const connectorLabelStyle: CSSProperties = {
    color: 'var(--text-tertiary)',
}
