/**
 * Barrel export for the AI-generated Balanced Scorecard strategy map.
 *
 * Components live here so they can be imported as
 * `@/components/strategy-map`. Used by both the live analysis page
 * (`AnalysisDetail.tsx`) and the print path (`PrintReport.tsx` via
 * a separate `PrintStrategyMap` shell — note: print continues to use
 * the verbose layout in `components/print/PrintStrategyMap.tsx`, NOT
 * these screen components).
 *
 * Screen rendering uses the graphical 2D React Flow canvas — see
 * `StrategyMapCanvas` for the canvas itself, `StrategyMapNode` for
 * the custom node, `StrategyMapHeader` for the band above the canvas.
 */
export { default as StrategyMapView } from './StrategyMapView'
export { default as StrategyMapCanvas } from './StrategyMapCanvas'
export { default as StrategyMapHeader } from './StrategyMapHeader'
export { default as StrategyMapNode } from './StrategyMapNode'
export { default as DeepDiveCTA } from './DeepDiveCTA'
export { default as WhatsMissingPanel } from './WhatsMissingPanel'
