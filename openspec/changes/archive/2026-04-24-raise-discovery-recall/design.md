## Context

Portfolio discovery = heuristic link extraction + AI page extraction, merged by URL domain. The heuristic path runs first and captures most of the obvious results; the AI path catches things the heuristic misses. The validation step then confirms each candidate is a real portfolio company.

Three layers each silently truncate the result:

```
 PAGE (e.g., 70 portfolio companies in HTML)
   │
   ├──▶ HEURISTIC EXTRACTION
   │      ├─ walks DOM, captures anchors
   │      ├─ _extract_context_name drops anchors with no derivable name   ← LEVER 2+3
   │      └─ _MAX_COMPANIES = 30 hard truncates                          ← LEVER 1
   │            │
   │            ▼
   │         ~30 companies
   │
   ├──▶ AI EXTRACTION
   │      ├─ receives page_text[:8000]  (≈half the page on large firms)  ← LEVER 4
   │      ├─ receives links[:100]
   │      └─ LLM returns companies found in the truncated slice
   │            │
   │            ▼
   │         ~48 companies
   │
   └──▶ MERGE (intersection auto / remainder validated)
          │
          ▼
       ~35 companies ← user sees
```

All four levers are local fixes — no new module, no new service, no API change.

## Goals / Non-Goals

**Goals:**
- Recover the missing ~35 companies on perotjain.com (and similar WordPress-driven PE sites) so the heuristic captures what the raw HTML contains.
- Keep validation in place so the extra candidates are filtered for false positives (funds, nav links, tools).
- Avoid any change to the async worker, SQS wiring, or frontend — this is a pure discovery-layer patch.
- Preserve existing tests; add new ones that would have caught the current gap.

**Non-Goals:**
- Do not replace or re-architect the discovery strategy (saved for `portfolio-discovery-deep`).
- Do not add card-pattern detection, JSON-LD extraction, or headless-browser scraping. Those are Levers 5-7, parked in the deep-discovery proposal.
- Do not change how validation works. The existing yes/no per-company AI call remains the sole precision mechanism.
- Do not add rate-limiting, per-firm quotas, or cost caps. If a firm has 300 real companies we validate all 300.

## Decisions

### Decision 1: Remove `_MAX_COMPANIES` entirely rather than raising it

Raising to 500 would still fail silently once exceeded. Removing the cap makes the heuristic path honest about what it found and lets the validation step decide precision. The async worker has a 15-minute budget; even 300 validation calls parallelized through `FutureManager` fit comfortably.

**Alternatives considered:**
- Raise to 500: preserves an artificial cap for unknown edge cases. Rejected — same failure mode, deferred.
- Cap by source page size: adds a heuristic on top of the heuristic. Rejected — more complexity, same benefit as removal.

### Decision 2: Name-derivation precedence order

When a link has no useful text (CTA like "LEARN MORE"), try name sources in this order. First non-empty wins.

```
1. <a title="...">                     ← explicit
2. <a aria-label="...">                ← explicit (unless containing "learn")
3. nearest ancestor <h1>…<h6>          ← card heading
4. nearest <img alt="...">  (non-empty) ← logo alt
5. nearest <img src="...">             ← NEW: filename-derived
6. URL domain of the anchor href       ← NEW: last-resort
```

Lever 2 adds rule 5. Lever 3 adds rule 6. The walk already stops at the first `article|section|li` to avoid bleeding into adjacent cards; both new rules respect that boundary.

**Why not put URL-domain first?**
- URL domain is the cheapest to compute but least accurate — `blinkeye.com` → "Blinkeye" is a worse name than "Blink Technologies" which we'd get from the img filename `blink-technologies.png`. Domain-derived names are a safety net, not a primary source.

**Why derive from img src at all vs just URL domain?**
- WordPress uploads preserve human-readable filenames (e.g., `access-healthcare.png`, `fold-health-logo.png`). These often match the real brand name (with hyphens/underscores) better than the bare domain.

### Decision 3: Filename-to-name parser

Given `https://.../wp-content/uploads/2022/09/accesshealthcare.png`, we need "Access Healthcare". Algorithm:

1. Take the basename (strip path + extension) → `accesshealthcare`
2. Strip common suffixes: `-logo`, `_logo`, `logo` at end → `accesshealthcare`
3. Split on `-` / `_` / camelCase boundaries → `["accesshealthcare"]` (no separators → single token)
4. If result is a single long lowercase token, leave as-is and title-case → "Accesshealthcare" (imperfect)
5. If result has multiple tokens, title-case each and join with space → "Access Healthcare"

Limitation acknowledged: single-word lowercase filenames (`accesshealthcare`) can't be split without a dictionary. In this case the AI validation step or the user (on the confirm screen) provides the real name. We don't try to be clever.

### Decision 4: URL-domain parser

Given `https://www.endurancelift.com/`, we want "Endurance Lift". Algorithm:

1. Parse URL, get hostname → `www.endurancelift.com`
2. Strip leading `www.` → `endurancelift.com`
3. Drop TLD → `endurancelift`
4. Same title-case handling as Decision 3

Same single-word limitation applies. Accepted.

### Decision 5: AI prompt truncation limits

| Field | Current | New | Rationale |
|-------|---------|-----|-----------|
| `page_text` | 8000 chars | 30000 chars | ~4× headroom for large portfolio pages; still well under model context limits (GPT-4o = 128k) |
| `links_text` | 3000 chars | 10000 chars | Matches expanded link-count |
| link count | 100 | 300 | Perotjain has ~70 portfolio links plus ~20-30 nav/footer; 300 gives comfortable cushion |

**Alternatives considered:**
- Remove truncation entirely: rejected — some malformed pages emit megabytes of boilerplate; unbounded input is a DoS waiting to happen.
- Dynamic truncation based on link count: rejected — added complexity for marginal benefit.

### Decision 6: No change to validation

`ValidatePortfolioCompanies` continues to run per-company yes/no AI calls on the non-intersection remainder. A larger remainder means more AI calls, but:
- Calls are parallel (`FutureManager`, 10 workers).
- Async worker accommodates the latency.
- Validation is the correct mechanism to filter false positives from an expanded candidate set; without it, our precision would fall with the recall increase.

## Risks / Trade-offs

- **[Risk] More candidates → more AI tokens → more cost.** On perotjain-scale firms, validation calls roughly double (22 → ~45). → Acceptable. The per-scan cost is still tiny relative to the product value. Monitor `ValidatePortfolioCompanies` step timings post-deploy; if latency approaches 10+ minutes per scan, revisit.
- **[Risk] Raising truncation exposes the AI path to malformed pages with megabyte-sized DOMs.** → Mitigation: the 30000-char limit is still a hard cap; it doesn't go away. Only the threshold moves.
- **[Risk] URL-domain-derived names might look ugly on the confirm screen** (e.g., "Endurancelift" for `endurancelift.com`). → Mitigation: the confirm UI already lets users edit/deselect. Better to show an imperfect name than to drop the company entirely.
- **[Risk] Removing the 30-cap might surface latent bugs in downstream code that quietly relied on "small N"** (e.g., scan record serialization, DynamoDB item size limits). → Mitigation: DynamoDB item max is 400KB, 300 companies × ~200 bytes each = 60KB, comfortably under. Test with a large synthetic fixture.
- **[Trade-off] Single-word lowercase filenames (`accesshealthcare`) still produce imperfect names** ("Accesshealthcare"). → Accepted. AI validation can correct this; user can correct on confirm screen.

## Migration Plan

1. Ship as a single backend PR — no frontend or infra changes.
2. Deploy to `development` account; run perotjain.com scan and diff against expected set of 70 companies.
3. Promote to `testing` → run a second scan, verify 60+ companies (accounting for validation filtering funds/tools).
4. Promote to `production`.
5. **No rollback concerns**: the changes are additive to recall. If precision regresses (validation lets through too many false positives), we can tighten the validation prompt — that's a separate, lower-risk lever.

## Open Questions

- **Should we filter "funds" out from portfolio results?** perotjain lists ~6 fund entries (Prime Movers Lab, Shield Capital, etc.). Current AI validation treats these as portfolio companies because they technically are investments. If the user explicitly doing operating-company diligence, they'd want funds excluded. **Recommendation:** leave for the confirm screen — user can deselect. Add to `portfolio-discovery-deep` for structured handling.
- **Should we log dropped candidates** (e.g., links that failed all 6 name-derivation rules) at INFO level so we can see what's slipping through? **Recommendation:** yes, already done by existing `logger.info("Dropping CTA link...")`. No change needed.
