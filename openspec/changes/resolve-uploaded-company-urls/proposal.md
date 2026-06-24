# Resolve URLs for name-only uploaded companies

## Why

The CSV/PDF upload (and manual add) accept a company **name with an optional
URL** — that's the advertised format. But a company can only be analyzed with an
`http(s)` URL, so name-only rows can't be scanned.

The **silent-drop bug** this caused (name-only rows were pre-selected, counted in
"Analyze N", then discarded at confirm) is fixed separately: url-less rows are now
unselectable, excluded from the count, and a note explains they need a URL. That
fix makes the gap **honest** but doesn't **close** it — a customer who uploads a
list of just names still has to find and paste each URL by hand.

This change closes the gap: resolve a company name to its official website URL so
name-only uploads become analyzable, delivering on the "URL optional" promise.

## What changes (when built)

- A resolution step that takes url-less uploaded/added company names and grounds
  each to an official URL (reusing the grounded web-search path used elsewhere in
  discovery), entering the **needs-validation** tier — resolved URLs are
  candidates to confirm, not asserted facts.
- The confirmation screen offers "Find URLs for N companies" (or resolves on
  upload), then the customer reviews/edits before analysis.
- Low-confidence / ambiguous resolutions are surfaced for the customer to confirm
  rather than auto-accepted (avoid resolving "Acme" to the wrong `acme.com`).

## Open questions (resolve when scheduled)

- Accuracy/ambiguity: common names resolve to the wrong company — needs a
  confidence threshold + customer confirmation, not silent auto-fill.
- Cost/latency: one grounded lookup per name; batch + cap.
- UX: resolve-on-upload vs. an explicit "Find URLs" action on the confirm screen.

## Impact

- Affected spec: `portfolio-company-list-upload` (adds name→URL resolution).
- Affected code (when built): a resolution step/handler + a confirm-screen
  affordance; reuses the existing grounded-search + needs-validation merge path.
- Status: **backlog / not scheduled.** Companion to the now-shipped honest fix.
