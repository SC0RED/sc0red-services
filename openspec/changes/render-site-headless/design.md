# Design — Render-the-site headless rung (infra findings)

Captured from an explore session. **Not a commitment** — this records the
constraints and the open fork so the eventual ADR starts from facts, not a blank
page.

## Where it fits (low-risk — the pattern exists)

`render` is another additive escalation, identical in shape to `deepen` and
`source-url`:

```text
Confirm screen → POST /api/scan/{id}/render → SQS → worker _process_additive_merge
   → RenderSiteStep:  assert_public_url → <render to post-JS HTML> → extract_companies_from_scrape
                      → find_new_candidates / merge / build_verdict (source="render", needs_validation)
   → awaiting_confirmation (augmented list + verdict)
```

Almost all reuse. The only new surface is **"URL → post-JS DOM"** (step + its
infra). Value is specifically **client-side-rendered firms** where `curl_cffi`
returns an empty shell and JS paints the portfolio after load.

## Packaging constraint (the hard one)

All Lambdas are **ZIP-packaged** (`lambda_.Function` + `Code.from_asset("../backend",
bundling=…)`), which caps the deployment package at **250 MB unzipped** (code +
layers). Headless Chromium is ~300 MB+ on disk plus system libs — **it cannot fit
the zip model.** So "add it to the worker" is impossible, and the options are:

1. **Self-hosted Chromium in a NEW container-image Lambda** (10 GB limit).
   Separate function is mandatory here — different packaging from the zip worker,
   plus isolation (render is rare/heavy; analysis/discovery run constantly) and
   independent memory/`/tmp`/timeout tuning. Cleanest shape: a pure "URL →
   rendered HTML" service the worker invokes synchronously.
2. **Managed browser API** (Browserless / ScrapingBee / Bright Data). NO new
   Lambda — the existing zip worker just HTTP-calls it. Fastest to ship; per-call
   cost + external dependency; the (public) firm URL leaves our infra.

Sizing (self-host, ballpark — pin real numbers in the spike): memory ~2–3 GB
(worker is already 2048 MB), cold start +2–5 s (Chromium init), per render ~3–15 s
(well under the 900 s ceiling; cap ~30–60 s), `/tmp` bumped to ~1–2 GB. Compute
cost ~sub-cent/render at opt-in volume.

**Recommendation (to validate):** start with a **managed browser API**. It
delivers the CSR-firm value without the Chromium-in-Lambda ops investment (image
pipeline, Chromium upkeep, cold-start/`/tmp` tuning); migrate to self-hosted later
if volume/cost/data-residency demands. The escalation plumbing is identical either
way, so it's not a lock-in.

## Architecture: cloud is uniformly arm64

**Updated for the `arm64-lambda-fleet` change** (the fleet moved to arm64). The
explore session originally found the cloud on x86_64 (the `development` *branch*
deploys the `staging` *config*); `arm64-lambda-fleet` then flipped all cloud
configs to arm64 and moved the bundling `deploy` jobs to `ubuntu-24.04-arm` so the
aarch64 bundle is built natively.

| config key | arch | deployed by |
|---|---|---|
| `development` | arm64 | local `cdk deploy` (Apple-Silicon Mac) |
| `staging` (the cloud "dev") | arm64 | deploy-backend.yml on `ubuntu-24.04-arm` |
| `testing` | arm64 | deploy-testing.yml on `ubuntu-24.04-arm` |
| `production` | arm64 | deploy-production.yml on `ubuntu-24.04-arm` |

So local + all cloud envs are now **arm64**, built on arm64 runners — the
former implicit bundle↔runner-arch coupling is resolved (the runner arch is
pinned in the workflows).

Implications for render-site:
- The Chromium image (or any arch-specific binary) targets **arm64** for all
  envs — a **single image**, platform-pinned to `linux/arm64`. No per-env split.
- Pin the image platform explicitly regardless — don't inherit "whatever the
  runner is."

## Spikes to run before committing (ADR inputs)

1. **Does render beat search-deeper/upload?** On 2–3 known-CSR firms, does the
   rendered DOM actually expose the portfolio, or is it lazy-loaded / paginated /
   behind scroll/click? De-risks the whole feature in ~a day.
2. **Self-host vs managed** decision (cost at expected volume, data-residency,
   SSRF posture).
3. **SSRF in a browser:** sub-resource/iframe fetches are harder to guard than a
   single curl. Decide policy (reuse `assert_public_url` for the top URL;
   constrain redirects/sub-resources).

## Related, separate

The bundle↔runner-arch coupling has since been addressed by `arm64-lambda-fleet`
(deploy jobs pinned to arm64 runners, fleet on arm64). A future `--platform`/
`--only-binary` pin would make it robust against a runner-arch change, but it's no
longer load-bearing for render-site — the Chromium image just targets arm64.
