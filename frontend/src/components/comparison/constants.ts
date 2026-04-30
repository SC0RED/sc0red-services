/**
 * Comparison overlay colors as CSS variables — flip with the active theme.
 * Recharts accepts `var(...)` strings for `stroke` / `fill` on modern browsers.
 * Use {@link COMPARISON_COLOR_TOKENS} when you need a resolved hex string
 * (canvas rendering, color math, PDF export, etc).
 */
export const COMPARISON_COLORS = ['var(--accent-blue)', 'var(--risk-moderate)', 'var(--risk-low)']

export const COMPARISON_COLOR_TOKENS = ['--accent-blue', '--risk-moderate', '--risk-low'] as const
