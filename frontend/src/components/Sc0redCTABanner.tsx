'use client'

import { useState } from 'react'

import { emit } from '@/lib/analytics/emitEvent'
import type { ActiveLeverFilter } from '@/lib/types/analytics'

interface Sc0redCTABannerProps {
    contactUrl: string
    analysisId: string
    opportunityCount: number
    activeLeverFilter: ActiveLeverFilter | null
}

/**
 * Expandable sc0red call-to-action banner rendered at the bottom of the
 * opportunities list. Collapsed by default — one line with a chevron.
 * Expanded — pitch copy + an external link to the sc0red contact page.
 *
 * Emits three analytics events via `POST /api/analytics/events`:
 * - `sc0red_cta_banner_expanded` — toggle opens
 * - `sc0red_cta_banner_collapsed` — toggle closes
 * - `sc0red_cta_clicked` — "Start the conversation" link click
 *
 * Emit failures never block the UI (see `lib/analytics/emitEvent`).
 *
 * See openspec/changes/opportunities-cta-analytics for the full spec.
 */
export default function Sc0redCTABanner({
    contactUrl,
    analysisId,
    opportunityCount,
    activeLeverFilter,
}: Sc0redCTABannerProps) {
    const [isOpen, setIsOpen] = useState(false)
    const controlsId = 'sc0red-cta-details'

    const analyticsContext = {
        analysisId,
        opportunityCount,
        activeLeverFilter,
    }

    const handleToggle = () => {
        const next = !isOpen
        setIsOpen(next)
        // Fire-and-forget — the visual toggle is instant, the emit is best-effort.
        void emit(next ? 'sc0red_cta_banner_expanded' : 'sc0red_cta_banner_collapsed', analyticsContext)
    }

    const handleCtaClick = () => {
        // Fire-and-forget. The browser dispatches the anchor's default
        // navigation as soon as this handler returns — awaiting a Promise
        // here would NOT delay navigation (React does not suspend the
        // default action for async handlers). We rely on `keepalive: true`
        // inside `emit()` so the POST completes even if the new tab opens
        // before the fetch resolves. The current tab also stays open
        // (target="_blank"), so the fetch's owning document is not torn
        // down either way.
        void emit('sc0red_cta_clicked', analyticsContext)
    }

    return (
        <div
            className="card"
            style={{
                marginTop: '1.5rem',
                overflow: 'hidden',
                borderTop: '3px solid var(--accent-blue)',
                background: 'var(--bg-surface-3)',
            }}
        >
            <button
                onClick={handleToggle}
                aria-expanded={isOpen}
                aria-controls={controlsId}
                className="sc0red-cta-toggle"
                style={{
                    width: '100%',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '1.25rem',
                    textAlign: 'left',
                }}
            >
                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '1rem',
                    }}
                >
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.75rem',
                            flex: 1,
                        }}
                    >
                        <span
                            aria-hidden="true"
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                width: '28px',
                                height: '28px',
                                borderRadius: '50%',
                                background: 'rgba(59,123,246,0.15)',
                                color: 'var(--accent-blue)',
                                fontSize: '0.95rem',
                                fontWeight: 700,
                                flexShrink: 0,
                            }}
                        >
                            ◆
                        </span>
                        <span
                            style={{
                                fontWeight: 600,
                                fontSize: '0.95rem',
                                color: 'var(--text-primary)',
                            }}
                        >
                            Dig deeper with a sc0red advisor
                        </span>
                    </div>
                    <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="var(--text-tertiary)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        style={{
                            transform: isOpen ? 'rotate(180deg)' : 'none',
                            transition: 'transform 0.2s',
                            flexShrink: 0,
                        }}
                    >
                        <polyline points="6 9 12 15 18 9" />
                    </svg>
                </div>
            </button>

            {isOpen && (
                <div id={controlsId} style={{ padding: '0 1.25rem 1.5rem' }}>
                    <div className="divider" style={{ marginBottom: '1.25rem' }} />
                    <p
                        style={{
                            fontSize: '0.9rem',
                            lineHeight: 1.75,
                            color: 'var(--text-primary)',
                            marginBottom: '1.25rem',
                        }}
                    >
                        Our PE-experienced advisors take you from this analysis to operational results — from
                        positioning strategy through production deployment, faster than traditional advisory
                        timelines.
                    </p>
                    <a
                        href={contactUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={handleCtaClick}
                        className="sc0red-cta-button"
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            padding: '0.625rem 1.25rem',
                            borderRadius: 'var(--radius-md)',
                            background: 'var(--accent-blue)',
                            color: 'white',
                            fontSize: '0.875rem',
                            fontWeight: 600,
                            textDecoration: 'none',
                        }}
                    >
                        Start the conversation
                        <span aria-hidden="true">→</span>
                    </a>
                </div>
            )}
        </div>
    )
}
