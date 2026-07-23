'use client'

import { Command } from 'cmdk'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

import type { AnalysisItem, ScanItem } from '@/lib/types/api'
import { prettifyUrl } from '@/lib/utils/url'

import { useShortcutsUi } from './ShortcutsUi'

/**
 * Cmd-K command palette — Tier 1 §5.
 *
 * Three result categories:
 *   1. Companies — fuzzy-search over the user's analyses by name.
 *   2. Portfolios — recent portfolio scans by source URL.
 *   3. Actions — static top-level navigation (New scan, Settings, etc.)
 *
 * Built on `cmdk` (Vercel's headless command palette) — small (~3 KB
 * gzipped), accessibility-correct out of the box, and the convention
 * across modern SaaS dashboards. See design D2.
 *
 * Data is lazy-fetched on first open and cached for the session. When
 * the user re-opens the palette later, they see whatever was loaded
 * the first time. This is intentional for v1 — server-side palette
 * search is a Tier 2 item; today's data volumes don't justify the
 * extra round-trip.
 */
export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
    const router = useRouter()
    const { openShortcuts } = useShortcutsUi()
    const [analyses, setAnalyses] = useState<AnalysisItem[]>([])
    const [scans, setScans] = useState<ScanItem[]>([])
    const [loaded, setLoaded] = useState(false)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        // Re-run only when `open` or `loaded` change. Excluding `loading`
        // from the deps prevents a re-render loop with the .finally below
        // (loading→false triggers re-render → re-effect → re-fetch).
        if (!open || loaded) return
        let cancelled = false
        let analysesFailed = false
        let dashboardFailed = false
        setLoading(true)
        Promise.all([
            fetch('/api/analyses')
                .then((r) => {
                    if (!r.ok) {
                        analysesFailed = true
                        return { analyses: [] }
                    }
                    return r.json()
                })
                .catch(() => {
                    analysesFailed = true
                    return { analyses: [] }
                }),
            fetch('/api/dashboard')
                .then((r) => {
                    if (!r.ok) {
                        dashboardFailed = true
                        return { recentScans: [] }
                    }
                    return r.json()
                })
                .catch(() => {
                    dashboardFailed = true
                    return { recentScans: [] }
                }),
        ])
            .then(
                ([analysesData, dashboardData]: [
                    { analyses?: AnalysisItem[] },
                    { recentScans?: ScanItem[] },
                ]) => {
                    if (cancelled) return
                    setAnalyses(analysesData.analyses ?? [])
                    setScans(
                        (dashboardData.recentScans ?? []).filter((s: ScanItem) => s.type === 'portfolio')
                    )
                    // Only mark the cache populated when at least one source
                    // returned successfully. If BOTH failed, leave `loaded`
                    // false so the next palette open re-attempts the fetch
                    // (transient network failures recover) instead of being
                    // stuck on an empty cache for the rest of the session.
                    // (Self-review MEDIUM 2 on PR #189.)
                    if (!analysesFailed || !dashboardFailed) {
                        setLoaded(true)
                    }
                }
            )
            .finally(() => {
                // Reset `loading` whether or not the fetch was cancelled.
                // If we skipped this on cancel, closing the palette mid-
                // fetch would leave loading=true forever; once `loading`
                // was a guard in the deps array it caused a stuck-state
                // bug for the rest of the session. (Self-review MEDIUM 1.)
                setLoading(false)
            })
        return () => {
            cancelled = true
        }
    }, [open, loaded])

    function navigate(href: string) {
        onOpenChange(false)
        router.push(href)
    }

    if (!open) return null

    return (
        <div
            className="cmdk-backdrop"
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            onClick={(event) => {
                // Close on backdrop click, but not on clicks inside the palette body
                if (event.target === event.currentTarget) onOpenChange(false)
            }}
        >
            <Command className="cmdk-root" loop>
                <Command.Input
                    autoFocus
                    placeholder="Search companies, portfolios, or actions..."
                    className="cmdk-input"
                />
                <Command.List className="cmdk-list">
                    {loading && <Command.Loading>Loading…</Command.Loading>}
                    <Command.Empty>No results.</Command.Empty>

                    <Command.Group heading="Actions" className="cmdk-group">
                        <PaletteAction
                            value="new-scan"
                            label="New scan"
                            hint="Start an analysis"
                            onSelect={() => navigate('/scan/new')}
                        />
                        <PaletteAction
                            value="dashboard"
                            label="Dashboard"
                            onSelect={() => navigate('/dashboard')}
                        />
                        <PaletteAction
                            value="analyses"
                            label="Analyses"
                            onSelect={() => navigate('/analyses')}
                        />
                        <PaletteAction value="team" label="Team" onSelect={() => navigate('/team')} />
                        <PaletteAction
                            value="connect ai mcp"
                            label="Connect AI"
                            hint="Connect an assistant over MCP"
                            onSelect={() => navigate('/connect')}
                        />
                        <PaletteAction
                            value="settings"
                            label="Settings"
                            onSelect={() => navigate('/settings')}
                        />
                        <PaletteAction
                            value="keyboard shortcuts help"
                            label="Keyboard shortcuts"
                            hint="?"
                            onSelect={openShortcuts}
                        />
                    </Command.Group>

                    {analyses.length > 0 && (
                        <Command.Group heading="Companies" className="cmdk-group">
                            {analyses.slice(0, 50).map((analysis) => (
                                <Command.Item
                                    key={analysis.id}
                                    value={`company-${analysis.companyName}-${analysis.id}`}
                                    onSelect={() => navigate(`/analysis/${analysis.id}`)}
                                    className="cmdk-item"
                                >
                                    <span>{analysis.companyName || 'Unnamed company'}</span>
                                    {analysis.industry && (
                                        <span className="cmdk-item-meta">{analysis.industry}</span>
                                    )}
                                </Command.Item>
                            ))}
                        </Command.Group>
                    )}

                    {scans.length > 0 && (
                        <Command.Group heading="Portfolios" className="cmdk-group">
                            {scans.slice(0, 20).map((scan) => (
                                <Command.Item
                                    key={scan.id}
                                    value={`portfolio-${scan.sourceUrl}-${scan.id}`}
                                    onSelect={() => navigate(`/portfolio/${scan.id}`)}
                                    className="cmdk-item"
                                >
                                    <span>{prettifyUrl(scan.sourceUrl)}</span>
                                    {typeof scan.totalCompanies === 'number' && (
                                        <span className="cmdk-item-meta">
                                            {scan.totalCompanies} companies
                                        </span>
                                    )}
                                </Command.Item>
                            ))}
                        </Command.Group>
                    )}
                </Command.List>
            </Command>
        </div>
    )
}

interface CommandPaletteProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

/** Compact palette-row for a static action. */
function PaletteAction({
    value,
    label,
    hint,
    onSelect,
}: {
    value: string
    label: string
    hint?: string
    onSelect: () => void
}) {
    return (
        <Command.Item value={value} onSelect={onSelect} className="cmdk-item">
            <span>{label}</span>
            {hint && <span className="cmdk-item-meta">{hint}</span>}
        </Command.Item>
    )
}
