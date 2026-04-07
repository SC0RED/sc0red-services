/**
 * Web Vitals reporting — logs Core Web Vitals to the browser console.
 *
 * Metrics collected:
 * - LCP  (Largest Contentful Paint) — time to render main content
 * - CLS  (Cumulative Layout Shift) — visual stability
 * - INP  (Interaction to Next Paint) — responsiveness
 * - FID  (First Input Delay) — first interaction responsiveness
 * - TTFB (Time to First Byte) — server response time
 *
 * Thresholds (Google "Good" targets):
 *   LCP < 2.5s | CLS < 0.1 | INP < 200ms | FID < 100ms | TTFB < 800ms
 */

interface Metric {
    name: string
    value: number
}

const THRESHOLDS: Record<string, { good: number; poor: number }> = {
    LCP: { good: 2500, poor: 4000 },
    CLS: { good: 0.1, poor: 0.25 },
    INP: { good: 200, poor: 500 },
    FID: { good: 100, poor: 300 },
    TTFB: { good: 800, poor: 1800 },
}

function getRating(name: string, value: number): string {
    const threshold = THRESHOLDS[name]
    if (!threshold) return ''
    if (value <= threshold.good) return '🟢'
    if (value <= threshold.poor) return '🟡'
    return '🔴'
}

function formatValue(name: string, value: number): string {
    if (name === 'CLS') return value.toFixed(3)
    return `${Math.round(value)}ms`
}

export function reportWebVital(metric: Metric): void {
    const { name, value } = metric
    const rating = getRating(name, value)
    const formatted = formatValue(name, value)

    // eslint-disable-next-line no-console
    console.log(`[Web Vitals] ${rating} ${name}: ${formatted}`)
}
