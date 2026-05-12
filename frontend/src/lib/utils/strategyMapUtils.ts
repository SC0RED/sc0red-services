import type { StrategyMap } from '@/lib/types/api'

/**
 * Shared utilities for rendering strategy-map content. Imported by
 * both the screen view (`components/strategy-map/StrategyMapView.tsx`)
 * and the print view (`components/print/PrintStrategyMap.tsx`) so
 * label conventions stay aligned across surfaces.
 */

const VALUE_PROPOSITION_LABELS: Record<string, string> = {
    operational_excellence: 'Operational Excellence',
    customer_intimacy: 'Customer Intimacy',
    product_leadership: 'Product Leadership',
    hybrid: 'Hybrid',
}

/**
 * Format a value-proposition classification for display.
 *
 * Hybrid classifications expand to "Hybrid (with <secondary>)" so
 * the reader can see both legs of the strategy in one glance,
 * matching the canonical Mobil HBR case (customer intimacy + ops
 * excellence). Unknown enum values fall back to the raw string,
 * which prevents a future API addition from breaking the UI before
 * the labels map is updated.
 */
export function formatValueProposition(
    primary: StrategyMap['valueProposition']['primary'],
    secondary?: StrategyMap['valueProposition']['secondary']
): string {
    const primaryLabel = VALUE_PROPOSITION_LABELS[primary] ?? primary
    if (primary === 'hybrid' && secondary) {
        return `${primaryLabel} (with ${VALUE_PROPOSITION_LABELS[secondary] ?? secondary})`
    }
    return primaryLabel
}
