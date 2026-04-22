## 1. Wire env-configurable contact URL

- [x] 1.1 Add `NEXT_PUBLIC_SC0RED_CONTACT_URL` to `frontend/.env.local.example` with the default value `https://www.sc0red.com/contact` and a comment explaining it's optional
- [x] 1.2 Add a resolver to `frontend/src/lib/config.ts` (single-file pattern already used by this module): `getSc0redContactUrl()` returns `process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL` if truthy, otherwise the `SC0RED_CONTACT_URL_DEFAULT` constant. Treat empty string / whitespace as falsy.
- [x] 1.3 Env var is read at code level only. The Amplify build grep (`env | grep -E '^(NEXTAUTH_|BACKEND_URL|NEXT_PUBLIC_)'`) copies any matching env vars from the build environment to `.env.production` — **but** no value is currently injected into the Amplify branch environment via CDK, so the default is used for all deployed builds today. Per-environment override at the CDK level is a fast-follow — see tasks below (section 8).

## 2. Create the sc0red CTA banner component

- [ ] 2.1 Create `frontend/src/components/Sc0redCTABanner.tsx` as a client component (`"use client"`)
  - Takes `contactUrl: string` as a prop (keeps the component pure and testable)
  - Collapsed state: single row with ◆ icon + "sc0red can help you capture these opportunities" + chevron
  - Expanded state: same header + pitch paragraph + "Start the conversation →" button styled as a link-button
  - Uses `aria-expanded` + `aria-controls` matching the existing opportunity-card pattern
  - External link uses `target="_blank"` + `rel="noopener noreferrer"`
  - Styling: accent background (distinct from opportunity cards), 3px blue top-border or left-border, uses existing CSS tokens (`var(--bg-surface-3)`, `var(--accent-blue)`, `var(--radius-md)`)
- [x] 2.2 Copy for initial version:
  - **Collapsed heading:** "sc0red can help you capture these opportunities"
  - **Expanded body:** "Our AI specialists implement opportunities like these end-to-end — from strategy through production deployment — moving faster than traditional enterprise timelines."
  - **CTA:** "Start the conversation →"
  - (No timeline commitment — pre-committing without knowing scope is risky. "Faster than traditional enterprise timelines" is confident but non-specific.)

## 3. Wire the banner into OpportunitiesList

- [ ] 3.1 In `frontend/src/components/OpportunitiesList.tsx`, import the banner and `getSc0redContactUrl`
- [ ] 3.2 Rename the per-card section label from "Implementation Partners" to "Tech Stack" (single literal at line 331)
- [ ] 3.3 Render `<Sc0redCTABanner contactUrl={getSc0redContactUrl()} />` after the last opportunity card, gated on `filteredOpps.length > 0`

## 4. Mirror changes in the PDF export

- [ ] 4.1 In `frontend/src/app/api/export/pdf/[analysisId]/route.ts` (lines 145-152), rename "Implementation Partners" → "Tech Stack"
- [ ] 4.2 After the opportunities loop closes, render a static sc0red CTA block containing:
  - Header: "sc0red can help you capture these opportunities"
  - Body pitch copy (same as the React banner's expanded state)
  - Contact URL rendered as visible text (not just a hyperlink) on its own line
  - Only render the block if the opportunities array is non-empty
- [ ] 4.3 Use a dedicated CSS class (e.g. `.sc0red-cta`) defined in the existing inline stylesheet — distinct background, matches the banner's visual weight
- [ ] 4.4 Read the contact URL in the PDF route via `process.env.NEXT_PUBLIC_SC0RED_CONTACT_URL || 'https://www.sc0red.com/contact'` (or import `getSc0redContactUrl` if it's SSR-safe)

## 5. Tests

- [ ] 5.1 Create `frontend/src/tests/components/Sc0redCTABanner.test.tsx`:
  - Renders the collapsed heading
  - Clicking the trigger toggles `aria-expanded` and reveals the pitch + CTA
  - The CTA link has the passed `contactUrl` as `href`, `target="_blank"`, and `rel` including `noopener` and `noreferrer`
- [ ] 5.2 Update `frontend/src/tests/components/OpportunitiesList.test.tsx`:
  - Existing assertion on "Accenture - AI strategy" stays — only the *heading* changes
  - Add assertion that the old heading "Implementation Partners" is no longer rendered
  - Add assertion that "Tech Stack" heading is rendered
  - Add assertion that the sc0red banner renders when `opportunities.length > 0`
  - Add assertion that the sc0red banner does NOT render when `opportunities` is empty (or the active-lever filter returns zero)
- [ ] 5.3 Confirm coverage floor (95%) still holds

## 6. Verify

- [ ] 6.1 `cd frontend && npm run lint` — no new errors
- [ ] 6.2 `cd frontend && npx tsc --noEmit` — no type errors
- [ ] 6.3 `cd frontend && npm test` — all tests pass
- [ ] 6.4 Manual: visit an analysis page with opportunities, confirm the "Tech Stack" rename, expand/collapse the banner, click the CTA (opens new tab, lands on `sc0red.com/contact`)
- [ ] 6.5 Manual: trigger a PDF export, open the PDF, confirm "Tech Stack" label and the closing sc0red block with a visible URL
- [ ] 6.6 Manual: apply a lever filter that returns zero opportunities — confirm the banner is not rendered

## 7. Final copy sign-off

- [x] 7.1 Copy reviewed: no hard timeline commitment (removed "60–90 days" claim — replaced with "faster than traditional enterprise timelines"). Heading and CTA button text kept from the initial draft.

## 8. Fast-follow (not part of this PR)

- [ ] 8.1 Wire `NEXT_PUBLIC_SC0RED_CONTACT_URL` through `infrastructure/stacks/amplify_construct.py` so per-environment overrides are possible (accept optional `sc0red_contact_url: str | None = None` on `create_branch()`, inject as `CfnBranch.EnvironmentVariableProperty` only when set). Only needed when we want a non-default URL in staging/production (not needed today — default is the production URL).
