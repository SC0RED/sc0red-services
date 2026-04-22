## Status

**Stub — deferred.** Placed in the radar as a follow-on to `opportunities-cta-sc0red`.

## Why

Once the sc0red CTA banner ships (see `opportunities-cta-sc0red`), we have no way to measure whether it works:

- How often does someone expand the banner vs. leave it collapsed?
- How often does an expansion convert to a click on "Start the conversation"?
- Which analyses / orgs / users drive the clicks?
- Does expansion/click rate differ per environment (staging vs. production)?

Without this data we're shipping a CTA blind and can't tell if the copy, placement, or visual treatment is working.

## What Changes (sketch — to be refined when this is picked up)

- **Emit analytics events** from the `Sc0redCTABanner` component:
  - `sc0red_cta_banner_expanded` (fires when user opens the banner)
  - `sc0red_cta_banner_collapsed` (optional — symmetry)
  - `sc0red_cta_clicked` (fires on the CTA link click, before navigation)
- **Same for the PDF export** — arguably we can't track PDF clicks directly, but we can emit a `sc0red_cta_rendered_in_pdf` event when the PDF is generated so we at least know how many PDFs carry the CTA.
- **Pick an analytics sink.** Options (decide when picking this up):
  - PostHog / Amplitude / Segment (SaaS)
  - AppSync / CloudWatch custom metric (stays in-AWS)
  - Backend API endpoint that writes to DynamoDB (simplest, no new vendor)
- **Include useful dimensions** in each event: `analysis_id`, `org_id`, `user_id`, `opportunity_count`, `active_lever_filter` (for expand/collapse — signals which view triggered engagement).
- **Respect user privacy.** No PII beyond the user ID already captured in the NextAuth session. No tracking of which specific opportunity was hovered/read.

## Capabilities

### New Capabilities
- `opportunities-cta-analytics`: Event tracking for sc0red CTA banner engagement across the web UI and PDF export.

## Impact (rough)

- **Depends on sink choice.** If we go with a backend endpoint, expect a new handler + DynamoDB write path + CDK changes (event table or metric). If we go with a SaaS vendor, expect a new client SDK, a secret to manage, and a privacy review.
- **Component change is small.** Adding `onExpand` / `onClick` handlers to `Sc0redCTABanner` that fire events is under 20 lines of code.
- **Copy of this proposal:** to be expanded into full `design.md` + `tasks.md` when picked up — this stub captures intent only.

## Non-Goals (for this stub)

- **Implementation.** This proposal is a placeholder until we decide to prioritize it. Do NOT start work on it without first promoting the stub to a full proposal.
- **A/B testing the CTA copy.** That's a separate concern — once we have analytics, we can scope A/B as its own proposal.
- **Cross-page analytics.** This proposal is specifically about the sc0red CTA surface. A broader "frontend analytics" strategy is a larger conversation.

## Next Step

When prioritized: convert this stub into a full proposal with `design.md` (sink choice, schema, privacy review) and `tasks.md`. Until then, leave it as a tracked placeholder.
