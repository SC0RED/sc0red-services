# Design — arm64 Lambda fleet

## The prerequisite: deterministic bundle architecture

The current bundling (`lambda_factory.build_bundling_options`) runs
`pip install . -t /asset-output` inside `python:3.12-slim` with **no platform
pin**, so it produces wheels for the **build-host** arch. An arm64 Lambda built by
the x86_64 CI would ship x86_64 wheels → native imports fail at load. So before
flipping the configs, the bundle must build for the target arch deterministically.
Three ways:

| Option | How | Pros | Cons |
|---|---|---|---|
| **C. arm64 CI runners** (recommended) | `runs-on: ubuntu-24.04-arm` in the deploy workflows; bundling builds natively | Native, fast, no pin gymnastics; local Mac (arm64) + CI (arm64) both build arm64 → uniform, fragility gone | Needs arm64 GitHub runners available to the org/repo (verify tier/cost) |
| **A. Pin pip to aarch64 wheels** | `pip install --platform manylinux2014_aarch64 --only-binary=:all: --target …` | No runner change | `--only-binary=:all:` fails if any (transitive) dep lacks an aarch64 wheel; `--platform` + a buildable local project is fiddly |
| **B. QEMU-emulated arm64 bundling** | CDK `BundlingOptions(platform="linux/arm64")` + `docker/setup-qemu-action` | Handles sdists (builds under emulation); no runner change | Emulated pip builds are **slow** (minutes); needs binfmt/QEMU on the runner |

**Lean: C** if arm64 runners are available — it's the clean, native answer and it
*also* eliminates the implicit coupling permanently (every build path is arm64).
Fall back to **A** (pin) if runners aren't an option and all deps have aarch64
wheels; **B** only if a dep is sdist-only on aarch64.

## Per-surface notes

- **API / worker / step-function helpers** — same bundling + `architecture` flip.
  No special handling.
- **MCP Lambda** — already arch-aware: `mcp_construct.py` selects
  `LambdaAdapterLayerArm64` when `architecture == ARM_64`. Flipping to arm64 picks
  the arm64 LWA layer automatically. (Confirms arm64 was partly anticipated.)
- **Native deps** — `curl-cffi` and `pydantic-core` publish aarch64 manylinux
  wheels. **Unknown:** `signalfield-core[all]` transitively (the `[all]` extra is a
  wildcard — could pull lxml/numpy/etc.). Verifying its aarch64 wheel coverage is
  the gating task; the first staging deploy will surface any gap as an ImportError.

## Rollout & validation

Use the normal promotion chain, staging first (it *is* the cloud "dev" env):

1. Land the bundle-arch fix + config flips on `development`.
2. **staging** deploy → confirm Lambdas report `arm64` (`aws lambda
   get-function-configuration … --query Architectures`), native imports load, a
   real portfolio scan runs (exercises curl-cffi), and the deployed E2E passes.
3. Promote → **testing** → confirm green.
4. Promote → **production** (auto-deploys) → confirm.

The native-dep risk is fully caught at step 2 before anything reaches prod.

## Risks

- **A dep without an aarch64 wheel** → bundling fails (option A) or runtime
  ImportError (caught at staging). Mitigation: verify wheel coverage up front;
  staging is the gate.
- **arm64 runner availability/cost** (option C) — verify before committing to it.
- **QEMU slowness** (option B) — only if forced onto emulation.
- Low overall risk: behaviour is unchanged, and staging catches arch issues before
  testing/prod.

## Explicitly not here

Render-site (separate change). Any application-logic change. Non-Lambda compute
(Amplify frontend, Step Functions state machine itself).
