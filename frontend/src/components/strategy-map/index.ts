/**
 * Barrel export for the AI-generated Balanced Scorecard strategy map.
 *
 * Components live here so they can be imported as
 * `@/components/strategy-map`. Used by both the live analysis page
 * (`AnalysisDetail.tsx`) and the print path (`PrintReport.tsx` via
 * a separate `PrintStrategyMap` shell).
 */
export { default as StrategyMapView } from './StrategyMapView'
export { default as DeepDiveCTA } from './DeepDiveCTA'
export { default as WhatsMissingPanel } from './WhatsMissingPanel'
export { default as ObjectiveCard } from './ObjectiveCard'
export { default as ConfidenceChip } from './ConfidenceChip'
export {
    CustomerPerspectiveRow,
    FinancialPerspectiveRow,
    InternalProcessesPerspectiveRow,
    OrganizationalCapacityRow,
} from './PerspectiveRow'
