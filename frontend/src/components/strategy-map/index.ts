/**
 * Barrel export for the AI-generated Balanced Scorecard strategy map.
 *
 * Components live here so they can be imported as
 * `@/components/strategy-map`. Used by both the live analysis page
 * (`AnalysisDetail.tsx` via `StrategyMapSlot`) and the print path
 * (`PrintStrategyMap.tsx`).
 *
 * Phase 6 of ``redesign-analysis-visuals`` (design D3) replaced the
 * React-Flow free-form canvas with a CSS-grid table — see
 * `StrategyMapTable` for the renderer, `StrategyMapView` for the
 * composition root (header + table + values strip). The previous
 * `StrategyMapCanvas` / `StrategyMapNode` pair was deleted in that
 * phase along with the `@xyflow/react` dependency.
 */
export { default as StrategyMapView } from './StrategyMapView'
export { default as StrategyMapHeader } from './StrategyMapHeader'
export { default as StrategyMapTable } from './StrategyMapTable'
export { default as DeepDiveCTA } from './DeepDiveCTA'
