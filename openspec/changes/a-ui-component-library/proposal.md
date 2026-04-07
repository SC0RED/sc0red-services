# Package A: UI Component Library

**Impact**: High | **Effort**: High | **Priority**: After Package D

## Problem

The frontend has no reusable UI primitives. Every component uses inline `style={}` objects, duplicating layout patterns hundreds of times. Destructive actions use browser `confirm()`. Form inputs have no error states. There are no skeleton loaders despite CSS existing for them.

This makes every frontend change slower and riskier — editing a button style requires touching dozens of files.

## Proposal

Create a small set of foundational UI components that replace the ad-hoc patterns used throughout the codebase.

## Components to create

### Primitives

| Component | Replaces | Key features |
|---|---|---|
| `Button` | Raw `<button className="btn ...">` | Variant (primary/secondary/ghost/danger), size, loading state, icon slot |
| `Input` | Raw `<input className="input">` | Error state (red border + message), label, helper text, required indicator |
| `Select` | Raw `<select>` | Consistent styling, error state |
| `Card` | Raw `<div className="card">` | Padding variants, header slot |
| `Badge` | Raw `<span className="badge ...">` | Variant from tier/type, consistent sizing |

### Composites

| Component | Replaces | Key features |
|---|---|---|
| `ConfirmDialog` | Browser `confirm()` | Modal overlay, title, message, confirm/cancel buttons, danger variant |
| `FormField` | Repeated label + input + error pattern | Wraps Input with label, validation message, required indicator |
| `Skeleton` | Nothing (missing today) | Skeleton variants: text, card, table row, stat card |
| `EmptyState` | Ad-hoc "no data" messages | Icon, title, description, action button |
| `LoadingSpinner` | Inline CSS animations | Consistent spinner with size variants |

### Patterns

| Pattern | Current | Proposed |
|---|---|---|
| Delete confirmation | `confirm('Are you sure?')` | `<ConfirmDialog variant="danger" />` |
| Form validation | Error shown after submit only | Real-time validation with `FormField` error state |
| Loading data | No indication or basic text | Skeleton placeholders matching content shape |
| Empty tables | Blank space | `EmptyState` with call to action |

## Migration approach

1. Create components in `frontend/src/components/ui/` directory
2. Add tests for each component
3. Migrate one page at a time (start with login → signup → dashboard)
4. Don't force-migrate every page at once — new components are available, old patterns still work

## What we DON'T do

- No design system documentation (Storybook) — that's Package F
- No theme system — stick with CSS variables
- No animation library — keep CSS transitions
- No form library (react-hook-form, formik) — simple controlled inputs are fine for our forms

## Success criteria

- [ ] All 5 primitive components created with tests
- [ ] All 5 composite components created with tests
- [ ] Delete operations use ConfirmDialog (not browser confirm)
- [ ] Login + signup + dashboard pages migrated to new components
- [ ] Form inputs show error states with red border + message
- [ ] At least 3 skeleton loader variants in use
