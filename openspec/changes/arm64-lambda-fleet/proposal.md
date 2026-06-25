# Move the cloud Lambda fleet to arm64 (Graviton)

## Why

Every **cloud** Lambda today is **x86_64** (the `staging` / `testing` /
`production` configs; only the local-`cdk-deploy` `development` config is arm64).
arm64/Graviton is **~20% cheaper per GB-second** at comparable performance. On the
**always-on API + worker** — the worker especially, billed for wall-clock at
2048 MB while it waits on AI calls — that ~20% compounds. (Render-site and other
rare paths are rounding-error; this is where the saving actually lives.)

Switching also fixes a latent fragility and a parity gap surfaced while exploring
render-site: the deploy bundle's wheel architecture is **implicitly coupled to the
CI runner arch** (`pip install .` in `python:3.12-slim`, no `--platform` pin →
host-arch wheels). It happens to hold today (arm64 only ever builds on a local
Mac, x86_64 only ever in CI), but it's undocumented and would silently break if a
runner arch changed. Making the bundle target the Lambda arch *deterministically*
turns that into an explicit invariant and lets us pick arm64 freely.

## What changes

- Make the deploy bundle build for the **target Lambda architecture
  deterministically**, independent of the CI runner arch (the prerequisite — see
  design.md for the options).
- Flip `lambda_architecture` to `arm64` for `staging`, `testing`, `production` in
  `infrastructure/app.py` (`development` is already arm64 → the whole fleet
  becomes uniform).
- Validate native deps load on arm64 (`curl-cffi`, `pydantic-core`, and whatever
  `signalfield-core[all]` pulls transitively).

## Impact

- Affected: `infrastructure/app.py` (configs), `infrastructure/stacks/lambda_factory.py`
  (`build_bundling_options`), possibly the deploy workflows (if moving to arm64
  runners). All five Lambda surfaces inherit the arch: API, worker, the three
  step-function helpers, and the MCP Lambda (whose LWA layer is **already**
  arch-conditional — `LambdaAdapterLayerArm64` vs `…X86`).
- Affected specs: new `lambda-deploy-architecture` (the bundle↔arch invariant).
- Behaviour: none — pure infra/cost change. No application logic touched.
- Out of scope: render-site (separate change); any non-Lambda compute.

## Expected benefit

~20% Lambda compute cost across the constant API/worker workload, uniform arch
across local + all cloud envs (restoring dev↔prod parity), and a robust,
explicit bundle-architecture contract.
