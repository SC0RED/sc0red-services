'use client'

import { useEffect, useMemo } from 'react'

import {
    PrintBackCover,
    PrintCover,
    PrintEbitdaOutline,
    PrintExecutiveSummary,
    PrintMethodologyAppendix,
    PrintOpportunityList,
    PrintRiskTable,
    PrintValueChainList,
} from '@/components/print'
import TopActionsCallout from '@/components/analysis/TopActionsCallout'
import { deriveSummary } from '@/lib/pdf/derivedSummary'
import { sortOpportunities } from '@/lib/pdf/sortOpportunities'
import type { AnalysisData } from '@/lib/types/api'

import '../print.css'

interface PrintReportProps {
    analysis: AnalysisData
}

/**
 * Composition root for the printed PDF.
 *
 * Section order matches the spec scenarios in
 * `openspec/changes/improve-pdf-export-content/specs/polished-pdf-export/spec.md`:
 *   Cover → Executive Summary → Top Actions → Risk Profile →
 *   AI Opportunity Roadmap → EBITDA Impact Model → Value Chain Analysis →
 *   Methodology → Back Cover
 *
 * Sections silently drop out when their source data is empty so a
 * sparse analysis still renders a clean PDF without blank headers or
 * empty pages. The orphan-page case (e.g. an analysis without
 * opportunities) is handled by each child component returning `null`
 * — `PrintReport` does not pre-filter the section order beyond that.
 *
 * The `useEffect` forces `<html data-theme="light">` so the headless
 * Chromium render picks up the light token palette. We ALSO set this
 * on the page-level CSS via the route's `print.css`; the `useEffect`
 * is the belt to that braces because `page.pdf()` does not go through
 * the `@media print` media query path.
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

    const riskScores = analysis.riskScores ?? []
    const topActions = analysis.topActions ?? []

    // Sort once at the top so every downstream section (executive
    // summary, opportunity list, EBITDA linkage, value-chain linkage)
    // sees the same printedIndex → opportunity mapping. Re-sorting per
    // section would desync the cross-references in the PDF.
    //
    // Reading `analysis.opportunities` *inside* the memo (rather than
    // `?? []`-ing first) keeps the dependency array stable — `?? []`
    // would mint a fresh empty array each render and bust the memo.
    const sortedOpportunities = useMemo(
        () => sortOpportunities(analysis.opportunities ?? []),
        [analysis.opportunities]
    )
    const summary = useMemo(
        () => deriveSummary(analysis, sortedOpportunities),
        [analysis, sortedOpportunities]
    )
    const opportunityCount = analysis.opportunities?.length ?? 0

    // Explicit 'en-US' locale — Puppeteer's Lambda container and the
    // developer's browser need to produce the SAME formatted string,
    // otherwise hydration warns. The print PDF is an English-only
    // artifact today; if/when localisation lands, this value moves to
    // a `useMemo` seeded from a deterministic UTC formatter.
    const generatedDate = new Date().toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
    })

    return (
        <main className="print-root">
            <PrintCover analysis={analysis} generatedDate={generatedDate} />

            <PrintExecutiveSummary summary={summary} />

            {topActions.length > 0 ? (
                <section className="print-section print-section--break-before">
                    <TopActionsCallout actions={topActions} />
                </section>
            ) : null}

            <PrintRiskTable riskScores={riskScores} />

            <PrintOpportunityList sortedOpportunities={sortedOpportunities} />

            {analysis.ebitdaTree ? (
                <PrintEbitdaOutline
                    ebitdaTree={analysis.ebitdaTree}
                    sortedOpportunities={sortedOpportunities}
                />
            ) : null}

            {analysis.valueChain && analysis.valueChain.steps.length > 0 ? (
                <PrintValueChainList
                    valueChain={analysis.valueChain}
                    sortedOpportunities={sortedOpportunities}
                />
            ) : null}

            <PrintMethodologyAppendix analysis={analysis} />

            <PrintBackCover hasOpportunities={opportunityCount > 0} />
        </main>
    )
}
