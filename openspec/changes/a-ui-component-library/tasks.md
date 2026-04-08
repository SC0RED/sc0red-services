# Tasks: UI Component Library

## PR 1: Create components + tests

### Primitives
- [x] Create `Button` component (variant, size, loading, icon, disabled)
- [x] Create `Input` component (error state, label, helper text)
- [x] Create `Select` component (consistent styling, error state)
- [x] Create `Card` component (padding variants, header slot)
- [x] Create `Badge` component (variant from tier/type)

### Composites
- [x] Create `ConfirmDialog` component (modal overlay, danger variant)
- [x] Create `FormField` component (wraps Input with label + error)
- [x] Create `Skeleton` component (text, card, table row, stat card variants)
- [x] Create `EmptyState` component (icon, title, description, action)
- [x] Create `LoadingSpinner` component (size variants)

### Tests
- [x] Tests for all primitive components (Button: 7, Input: 5)
- [x] Tests for all composite components (22 tests across Badge, Card, Select, FormField, EmptyState, LoadingSpinner, Skeleton, ConfirmDialog)

### CSS
- [x] Add error state styles to globals.css (input error border, error text)
- [x] Add dialog/modal overlay styles to globals.css
- [x] Skeleton styles already existed in globals.css

## PR 2: Migrate existing pages

- [ ] Migrate login page to use FormField, Button
- [ ] Migrate signup page to use FormField, Button, Select
- [ ] Migrate dashboard to use Card, Badge, EmptyState, Skeleton
- [ ] Replace browser confirm() with ConfirmDialog in DeleteAnalysisButton
- [ ] Replace browser confirm() with ConfirmDialog in DeleteScanButton
- [ ] Replace browser confirm() in invitation handlers (remove member, revoke invite)
