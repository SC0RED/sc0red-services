import { getSc0redContactUrl } from '@/lib/config'

interface PrintBackCoverProps {
    /** When false, the back cover is omitted entirely. */
    hasOpportunities: boolean
}

/**
 * Back-cover page — the single sc0red CTA for the entire PDF.
 *
 * Returns `null` when the analysis has no opportunities, so a sparse
 * report doesn't end with an out-of-context "we can help" page.
 *
 * The previous PDF rendered the CTA in two places (inline inside
 * `OpportunitiesList` and again inside `ValueChainDiagram`). Those
 * embedded CTAs are removed for the print path; this is the one
 * source of truth.
 */
export default function PrintBackCover({ hasOpportunities }: PrintBackCoverProps) {
    if (!hasOpportunities) return null

    const contactUrl = getSc0redContactUrl()

    return (
        <section
            className="print-section print-section--break-before"
            data-section="back-cover"
            style={{
                minHeight: 'calc(100vh - 64px)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                textAlign: 'center',
                gap: '20px',
            }}
        >
            <div
                style={{
                    fontSize: '0.875rem',
                    color: 'var(--accent-blue)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                }}
            >
                Next Steps
            </div>
            <h2 style={{ fontSize: '1.75rem', fontWeight: 800, margin: 0, maxWidth: '640px' }}>
                sc0red can help you capture these opportunities
            </h2>
            <p
                style={{
                    color: 'var(--text-secondary)',
                    lineHeight: 1.7,
                    maxWidth: '560px',
                    fontSize: '0.95rem',
                    margin: 0,
                }}
            >
                Our AI specialists implement opportunities like the ones in this report end-to-end — from
                strategy through production deployment — moving faster than traditional enterprise timelines.
            </p>
            <div style={{ marginTop: '12px' }}>
                <a
                    href={contactUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                        color: 'var(--accent-blue)',
                        fontWeight: 600,
                        fontSize: '0.95rem',
                        wordBreak: 'break-all',
                    }}
                >
                    {contactUrl}
                </a>
            </div>
        </section>
    )
}
