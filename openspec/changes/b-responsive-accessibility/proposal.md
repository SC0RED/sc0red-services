# Package B: Responsive Design & Accessibility

**Impact**: High | **Effort**: Medium | **Priority**: After Package A (parallel with C)

## Problem

The frontend has basic mobile support (sidebar collapse at 768px) but breaks on tablets, has no responsive grid adjustments, tables overflow horizontally, and dashboard stats are hardcoded 4-column. Accessibility has a good foundation (skip links, focus-visible, ARIA attributes) but gaps in ARIA live regions, SVG labels, and color-only risk indication.

## Proposal

Fix responsive breakpoints and close accessibility gaps so the app works correctly on tablet/mobile and meets WCAG AA.

## Responsive changes

### Breakpoints

| Breakpoint | Current | Proposed |
|---|---|---|
| > 1280px | None | Wide desktop — full layout |
| 1024px | Sidebar narrows | Sidebar narrows + grid adjusts |
| 768px | Mobile menu | Mobile menu + single column |
| < 480px | None | Compact mobile — stack everything |

### Specific fixes

1. **Dashboard stats grid**: `repeat(4, 1fr)` → responsive `repeat(auto-fit, minmax(200px, 1fr))`
2. **Tables**: Add horizontal scroll wrapper with shadow indicators, or card-based layout on mobile
3. **Comparison view**: Stack analyses vertically on mobile instead of side-by-side
4. **Value chain diagram**: Vertical layout on mobile, horizontal on desktop
5. **Form layouts**: Two-column forms (signup) → single column on mobile
6. **next/image**: Replace `<img>` tags with `next/image` for automatic responsive sizing + layout shift prevention

## Accessibility changes

1. **ARIA live regions**: Add `aria-live="polite"` to scan progress, loading states, and error messages
2. **SVG icon labels**: Add `aria-hidden="true"` on decorative SVGs, `aria-label` on actionable ones
3. **Risk tier indicators**: Add shape/pattern alongside color (e.g., icon or text always visible, not just on hover)
4. **Focus management**: After navigation, move focus to main content area
5. **Viewport meta**: Verify Next.js generates it correctly (it should by default, but confirm)

## What we DON'T do

- No mobile-first redesign — just make existing layout adapt
- No new navigation patterns for mobile (bottom nav, etc.)
- No WCAG AAA compliance — AA is the target
- No automated accessibility testing in CI (can add later)

## Success criteria

- [ ] Dashboard renders correctly at 480px, 768px, 1024px, 1280px
- [ ] Tables don't overflow — scroll or reflow on small screens
- [ ] All interactive SVG icons have accessible labels
- [ ] Scan progress announces updates via ARIA live region
- [ ] No `<img>` tags without width/height (use next/image)
- [ ] Lighthouse accessibility score ≥ 90
