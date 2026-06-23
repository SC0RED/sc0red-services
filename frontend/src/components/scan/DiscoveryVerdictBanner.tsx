import type { DiscoveryAction, DiscoveryCompleteness, DiscoveryVerdict } from '@/lib/types/scan'

interface DiscoveryVerdictBannerProps {
    verdict: DiscoveryVerdict
    /** Number of companies currently in the list (may differ from verdict.count
     *  after the customer edits/uploads), used in the plain-language message. */
    currentCount: number
    onUploadList: () => void
    onSearchDeeper: () => void
    uploadOpen: boolean
}

interface VerdictPresentation {
    tone: 'positive' | 'caution'
    title: string
    message: (count: number) => string
}

// completeness → how we explain the result to the customer. Mirrors the
// backend taxonomy in DiscoverPortfolio._build_verdict.
const PRESENTATION: Record<DiscoveryCompleteness, VerdictPresentation> = {
    full_site_list: {
        tone: 'positive',
        title: 'Portfolio read from the firm’s site',
        message: (count) =>
            `We read this firm’s portfolio directly from its website — ${count} ${plural(count)}. Review and deselect any you don’t want to analyze.`,
    },
    partial_site_list: {
        tone: 'caution',
        title: 'This may not be the full list',
        message: (count) =>
            `We found ${count} ${plural(count)} on the firm’s website, but some firms list only part of their portfolio on-site. If this looks short, search deeper or upload your full list.`,
    },
    web_search_exhausted: {
        tone: 'caution',
        title: 'No more found via search',
        message: (count) =>
            `Searching deeper found no companies beyond these ${count}. Web search can’t guarantee a complete list — upload the firm’s list to be sure nothing’s missing.`,
    },
    web_search_subset: {
        tone: 'caution',
        title: 'This list is likely incomplete',
        message: (count) =>
            `We couldn’t read this firm’s full portfolio from its site, so we used a quick web search — it found ${count} ${plural(count)} and this firm likely has more.`,
    },
    site_blocked: {
        tone: 'caution',
        title: 'We couldn’t reach the firm’s site',
        message: (count) =>
            `This firm’s website couldn’t be reached, so this list may be incomplete. A web search found ${count} ${plural(count)}.`,
    },
    genuinely_empty: {
        tone: 'caution',
        title: 'No portfolio companies found automatically',
        message: () =>
            'We couldn’t find this firm’s portfolio companies automatically. You can search deeper or upload the list yourself.',
    },
}

const ACTION_LABEL: Record<DiscoveryAction, string> = {
    upload_list: 'Upload a list',
    search_deeper: 'Search deeper',
    render_site: 'Render the site',
}

function plural(count: number): string {
    return count === 1 ? 'company' : 'companies'
}

export default function DiscoveryVerdictBanner({
    verdict,
    currentCount,
    onUploadList,
    onSearchDeeper,
    uploadOpen,
}: DiscoveryVerdictBannerProps) {
    const presentation = PRESENTATION[verdict.completeness]
    const positive = presentation.tone === 'positive'
    const accent = positive ? 'var(--risk-low)' : 'var(--risk-medium)'
    const accentBg = positive ? 'var(--risk-low-bg)' : 'var(--risk-medium-bg)'

    return (
        <div className="card" style={{ padding: '1.25rem 1.5rem', marginBottom: '1.25rem' }} role="status">
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
                <div
                    aria-hidden="true"
                    style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: 'var(--radius-md)',
                        background: accentBg,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        color: accent,
                        fontWeight: 700,
                    }}
                >
                    {positive ? '✓' : '!'}
                </div>
                <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>{presentation.title}</div>
                    <div
                        style={{
                            color: 'var(--text-secondary)',
                            fontSize: '0.875rem',
                            marginTop: '0.25rem',
                        }}
                    >
                        {presentation.message(currentCount)}
                    </div>
                    {verdict.siteSourceUrl && (
                        <div
                            style={{
                                color: 'var(--text-tertiary)',
                                fontSize: '0.8125rem',
                                marginTop: '0.375rem',
                            }}
                        >
                            ✓ Read from {verdict.siteSourceUrl.replace(/^https?:\/\//, '')}
                        </div>
                    )}
                </div>
            </div>

            {verdict.availableActions.length > 0 && (
                <div
                    style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: '0.5rem',
                        marginTop: '1rem',
                    }}
                >
                    {verdict.availableActions.map((action) => {
                        // An action is live only if it has a wired handler.
                        // upload_list and search_deeper are wired; render_site
                        // (Phase 3) stays disabled until its handler exists — so
                        // it can never become enabled-but-inert.
                        const handlers: Partial<Record<DiscoveryAction, () => void>> = {
                            upload_list: onUploadList,
                            search_deeper: onSearchDeeper,
                        }
                        const handler = handlers[action]
                        const live = handler !== undefined
                        return (
                            <button
                                key={action}
                                type="button"
                                onClick={handler}
                                disabled={!live}
                                aria-pressed={action === 'upload_list' ? uploadOpen : undefined}
                                className={live ? 'btn btn-secondary' : 'btn btn-ghost'}
                                style={{
                                    fontSize: '0.8125rem',
                                    padding: '0.375rem 0.75rem',
                                    cursor: live ? 'pointer' : 'not-allowed',
                                    opacity: live ? 1 : 0.6,
                                }}
                                title={live ? undefined : 'Coming soon'}
                            >
                                {ACTION_LABEL[action]}
                                {!live && (
                                    <span
                                        style={{
                                            marginLeft: '0.375rem',
                                            fontSize: '0.6875rem',
                                            color: 'var(--text-tertiary)',
                                        }}
                                    >
                                        soon
                                    </span>
                                )}
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
