'use client'

import type { Citation, ProvenanceTier } from '@/lib/types/api'

/**
 * "Show your work" caption for a researched FACT (fact-provenance-labeling spec).
 *
 * Renders a single honest-but-rigorous line: a provenance label, the confidence
 * level, the one-line basis, and — when the figure is `disclosed` — its source
 * citation(s). The goal is to make clear an estimate is reasoned and effortful,
 * not random, while staying honest that an estimate is an estimate.
 */
const TIER_LABEL: Record<ProvenanceTier, string> = {
    disclosed: 'Reported',
    industry_typical: 'Industry estimate',
    derived_estimate: 'Estimated',
}

interface ProvenanceCaptionProps {
    provenance?: ProvenanceTier | null
    confidenceLevel?: 'high' | 'medium' | 'low' | null
    basis?: string | null
    citations?: Citation[]
    testId?: string
}

function hostname(url: string): string {
    try {
        return new URL(url).hostname.replace(/^www\./, '')
    } catch {
        return url
    }
}

export default function ProvenanceCaption({
    provenance,
    confidenceLevel,
    basis,
    citations,
    testId,
}: ProvenanceCaptionProps) {
    // Nothing meaningful to show (e.g. legacy record without provenance).
    if (!provenance && !basis) return null

    const tier = provenance ? TIER_LABEL[provenance] : null
    const sources = citations ?? []

    return (
        <p
            data-testid={testId ?? 'provenance-caption'}
            style={{
                margin: '0.5rem 0 0',
                fontSize: '0.8rem',
                lineHeight: 1.5,
                color: 'var(--text-secondary)',
            }}
        >
            {tier && <strong>{tier}</strong>}
            {confidenceLevel && <span> · {confidenceLevel} confidence</span>}
            {basis && <span> — {basis}</span>}
            {sources.length > 0 && (
                <span>
                    {' · Source: '}
                    {sources.map((citation, index) => (
                        <span key={citation.url}>
                            {index > 0 && ', '}
                            <a href={citation.url} target="_blank" rel="noopener noreferrer">
                                {citation.title || hostname(citation.url)}
                            </a>
                        </span>
                    ))}
                </span>
            )}
        </p>
    )
}
