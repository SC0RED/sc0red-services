# Design — Render-the-site headless rung (infra findings)

Captured from an explore session. **Not a commitment** — this records the
constraints and the open fork so the eventual ADR starts from facts, not a blank
page.

## Where it fits (low-risk — the pattern exists)

`render` is another additive escalation, identical in shape to `deepen` and
`source-url`:

```
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

## Architecture: cloud is uniformly x86_64

Investigated during the explore session — corrects an earlier assumption:

| config key | arch | deployed by |
|---|---|---|
| `development` | arm64 | **local `cdk deploy` only** (no workflow) — matches an Apple-Silicon Mac |
| `staging` (the cloud "dev") | x86_64 | deploy-backend.yml (push `development`), CI x86_64 |
| `testing` | x86_64 | deploy-testing.yml, CI x86_64 |
| `production` | x86_64 | deploy-production.yml, CI x86_64 |

The `development` *branch* deploys the `staging` *config*, so every **cloud** env
is **x86_64**, built by x86_64 CI runners. Bundling does NOT pin a wheel platform
(`pip install .` in `python:3.12-slim` → host-arch wheels), so the Lambda arch
implicitly tracks the build-host arch — consistent today because arm64 only ever
builds locally and x86_64 only ever builds in CI.

Implications for render-site:
- The Chromium image (or any arch-specific binary) targets **x86_64** for all
  cloud envs — a **single image**, platform-pinned to `linux/amd64`. No per-env
  split. (The local arm64 `development` stack isn't a render target.)
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

The unpinned-bundling fragility (bundle arch coupled to runner arch) is a small
optional hardening — pin `--platform`/`--only-binary` — independent of render-site
but on the critical path for any future native-binary Lambda.
