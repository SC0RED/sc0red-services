'use client'

import dynamic from 'next/dynamic'
import { useEffect } from 'react'

import OpportunitiesList from '@/components/OpportunitiesList'
import RiskBreakdown from '@/components/RiskBreakdown'
import EbitdaSection from '@/components/analysis/EbitdaSection'
import TopActionsCallout from '@/components/analysis/TopActionsCallout'
import { getSc0redContactUrl } from '@/lib/config'
import type { AnalysisData } from '@/lib/types/api'
import { TIER_COLORS } from '@/lib/utils/riskUtils'

import '../print.css'

// ValueChainDiagram is loaded with `ssr: false` because it relies on
// browser-only refs. The headless browser running the print job has full
// browser context, so this loads cleanly during the Puppeteer render.
const ValueChainDiagram = dynamic(() => import('@/components/ValueChainDiagram'), {
    ssr: false,
    loading: () => null,
})

interface PrintReportProps {
    analysis: AnalysisData
}

/**
 * Print-optimised tree of the analysis. Forces the light theme on
 * `<html>` regardless of the user's screen preference (`@media print`
 * already covers Cmd+P; this `useEffect` covers headless-browser
 * `page.pdf()` which renders without going through the print media query).
 *
 * Section order matches the spec scenarios in
 * `openspec/changes/polished-pdf-export/specs/polished-pdf-export/spec.md`.
 */
export default function PrintReport({ analysis }: PrintReportProps) {
    useEffect(() => {
        const previous = document.documentElement.getAttribute('data-theme')
        document.documentElement.setAttribute('data-theme', 'light')
        return () => {
            // Restore the previous theme so a developer who navigated to the
            // print URL in their own browser doesn't end up locked in light
            // when they navigate away.
            if (previous) document.documentElement.setAttribute('data-theme', previous)
            else document.documentElement.removeAttribute('data-theme')
        }
    }, [])

    const tier = analysis.riskTier ?? 'moderate'
    const tierColor = TIER_COLORS[tier] ?? 'var(--text-secondary)'
    const opportunities = analysis.opportunities ?? []
    const riskScores = analysis.riskScores ?? []
    const topActions = analysis.topActions ?? []
    const generatedDate = new Date().toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
    })

    return (
        <main className="print-root">
            {/* Cover page */}
            <section className="print-cover">
                <div className="print-cover-eyebrow">sc0red · AI Risk Report</div>
                <h1 className="print-cover-title">{analysis.companyName}</h1>
                {analysis.companyUrl ? <p className="print-cover-meta">{analysis.companyUrl}</p> : null}
                {analysis.industry ? <p className="print-cover-meta">{analysis.industry}</p> : null}
                <div className="print-cover-score" style={{ borderColor: tierColor, color: tierColor }}>
                    {analysis.overallRiskScore != null ? analysis.overallRiskScore.toFixed(1) : '—'}
                </div>
                <div>
                    <span
                        className="badge"
                        style={{
                            background: 'var(--accent-blue-glow)',
                            color: tierColor,
                            border: `1px solid ${tierColor}`,
                            padding: '4px 12px',
                            borderRadius: '999px',
                            fontWeight: 600,
                            fontSize: '0.8125rem',
                            textTransform: 'uppercase',
                            letterSpacing: '0.04em',
                        }}
                    >
                        {tier} risk
                    </span>
                </div>
                {analysis.analysisSummary ? (
                    <p
                        style={{
                            marginTop: '24px',
                            maxWidth: '640px',
                            color: 'var(--text-secondary)',
                            lineHeight: 1.65,
                        }}
                    >
                        {analysis.analysisSummary}
                    </p>
                ) : null}
                <p
                    style={{
                        marginTop: '32px',
                        color: 'var(--text-tertiary)',
                        fontSize: '0.875rem',
                    }}
                >
                    Generated {generatedDate} · sc0red.com
                </p>
            </section>

            {/* Top 3 immediate actions */}
            {topActions.length > 0 ? (
                <section className="print-section">
                    <TopActionsCallout actions={topActions} />
                </section>
            ) : null}

            {/* Risk Assessment */}
            {riskScores.length > 0 ? (
                <section className="print-section">
                    <h2>Risk Assessment</h2>
                    <RiskBreakdown riskScores={riskScores} />
                </section>
            ) : null}

            {/* AI Opportunity Roadmap */}
            {opportunities.length > 0 ? (
                <section className="print-section print-section--break-before">
                    <h2>AI Opportunity Roadmap</h2>
                    <OpportunitiesList
                        opportunities={opportunities}
                        activeLever="All"
                        analysisId={analysis.id}
                    />
                </section>
            ) : null}

            {/* EBITDA Impact Model */}
            {analysis.ebitdaTree ? (
                <section className="print-section print-section--break-before print-ebitda">
                    <EbitdaSection ebitdaTree={analysis.ebitdaTree} opportunities={opportunities} />
                </section>
            ) : null}

            {/* Value Chain */}
            {analysis.valueChain && analysis.valueChain.steps.length > 0 ? (
                <section className="print-section print-section--break-before">
                    <h2>Value Chain Analysis</h2>
                    <ValueChainDiagram
                        steps={analysis.valueChain.steps}
                        opportunities={opportunities}
                        summary={analysis.valueChain.summary}
                    />
                </section>
            ) : null}

            {/* sc0red CTA — only when there's something to act on */}
            {opportunities.length > 0 ? (
                <section className="print-cta">
                    <div style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '8px' }}>
                        sc0red can help you capture these opportunities
                    </div>
                    <p
                        style={{
                            color: 'var(--text-secondary)',
                            lineHeight: 1.7,
                            margin: '0 0 12px',
                            fontSize: '0.9375rem',
                        }}
                    >
                        Our AI specialists implement opportunities like these end-to-end — from strategy
                        through production deployment — moving faster than traditional enterprise timelines.
                    </p>
                    <a
                        href={getSc0redContactUrl()}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                            color: 'var(--accent-blue)',
                            fontWeight: 600,
                            fontSize: '0.875rem',
                            wordBreak: 'break-all',
                        }}
                    >
                        {getSc0redContactUrl()}
                    </a>
                </section>
            ) : null}
        </main>
    )
}
