/**
 * Barrel export for the print-only component family.
 *
 * Print components live here (separate from the screen components in
 * the parent `components/` directory) so they can be imported as
 * `@/components/print` without leaking interactive UI primitives back
 * into the print path. The print route's `PrintReport.tsx` is the only
 * legitimate consumer; non-print pages should never import from here.
 */
export { default as PrintCover } from './PrintCover'
export { default as PrintStrategyMap } from './PrintStrategyMap'
export { default as PrintExecutiveSummary } from './PrintExecutiveSummary'
export { default as PrintRiskTable } from './PrintRiskTable'
export { default as PrintOpportunityCard } from './PrintOpportunityCard'
export { default as PrintOpportunityList } from './PrintOpportunityList'
export { default as PrintEbitdaOutline } from './PrintEbitdaOutline'
export { default as PrintValueChainList } from './PrintValueChainList'
export { default as PrintQuickWinsMatrix } from './PrintQuickWinsMatrix'
export { default as PrintMethodologyAppendix } from './PrintMethodologyAppendix'
export { default as PrintBackCover } from './PrintBackCover'
