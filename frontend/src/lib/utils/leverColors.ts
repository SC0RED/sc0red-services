/**
 * Lever-color palette as CSS variables — these flip with the active theme
 * via the `--lever-*` tokens declared in `globals.css`.
 *
 * Consumers that need a real hex string (canvas rendering, PDF export, color
 * math) should reach for `useThemedColor` against {@link LEVER_COLOR_TOKENS}.
 */
export const LEVER_COLORS: Record<string, string> = {
    'Revenue Side': 'var(--lever-revenue)',
    'Cost Side': 'var(--lever-cost)',
    Both: 'var(--lever-both)',
}

export const LEVER_COLOR_TOKENS: Record<string, string> = {
    'Revenue Side': '--lever-revenue',
    'Cost Side': '--lever-cost',
    Both: '--lever-both',
}
