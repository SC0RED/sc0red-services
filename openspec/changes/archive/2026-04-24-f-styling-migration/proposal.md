# Package F: Styling Migration

**Impact**: Lower (DX improvement) | **Effort**: High | **Priority**: Last (incremental)

## Problem

Every component uses inline `style={}` objects for layout, spacing, and colors — even though `globals.css` has a well-structured design system with utility classes. The same `display: 'flex', alignItems: 'center', gap: '1rem'` pattern appears hundreds of times. This makes the codebase harder to maintain and slower to develop in.

## Proposal

Incrementally migrate inline styles to CSS utility classes. This is a DX improvement — users won't see a difference, but developers will move faster.

## Approach options

### Option 1: Expand existing CSS utilities (recommended)

Add utility classes to `globals.css` that match the most common inline patterns:
```css
.flex { display: flex; }
.flex-center { display: flex; align-items: center; }
.flex-col { display: flex; flex-direction: column; }
.gap-sm { gap: 0.5rem; }
.gap-md { gap: 1rem; }
.gap-lg { gap: 1.5rem; }
.p-md { padding: 1rem; }
.p-lg { padding: 1.5rem; }
/* etc. */
```

Pros: No new dependencies, consistent with existing approach.
Cons: Manual, limited autocomplete.

### Option 2: Tailwind CSS

Replace inline styles with Tailwind classes: `className="flex items-center gap-4 p-4"`.

Pros: Industry standard, great DX with autocomplete, comprehensive.
Cons: Large migration, learning curve, config overhead, changes existing globals.css approach.

### Recommendation

**Option 1 for now.** The existing CSS variable system is solid. Adding 30-40 utility classes covers 80% of the inline style patterns. Tailwind is a bigger commitment that can come later if the team grows.

## Migration strategy

Don't migrate everything at once. Instead:
1. Add utility classes to `globals.css`
2. When touching a component for any other reason, migrate its styles
3. New components must use classes (no new inline styles)
4. Track migration progress: count of `style=` occurrences per file

## What we DON'T do

- No Tailwind (too large a migration for current team size)
- No CSS-in-JS (styled-components, emotion)
- No Storybook (useful but separate effort)
- No forced migration of all files at once

## Success criteria

- [ ] 30+ utility classes added to globals.css
- [ ] New components use CSS classes instead of inline styles
- [ ] At least 5 existing components migrated as examples
- [ ] `style=` count reduced by 30% across migrated files
