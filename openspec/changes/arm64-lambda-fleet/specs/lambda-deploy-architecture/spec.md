# Spec — lambda-deploy-architecture

## ADDED Requirements

### Requirement: The deploy bundle targets the Lambda architecture deterministically

The Lambda deployment bundle SHALL be built for the **target Lambda's
architecture**, independent of the CI/build-host architecture. Native wheels in
the package MUST match the architecture the function is configured to run on, so
the Lambda architecture can be chosen freely without risking a native-import
mismatch at runtime.

#### Scenario: arm64 Lambda is bundled with arm64 wheels
- **WHEN** a function is configured for arm64 and its asset is built (on any CI
  runner)
- **THEN** the bundle contains aarch64/manylinux wheels for all native
  dependencies, and the function loads them without error

#### Scenario: build-host architecture does not silently determine the bundle
- **WHEN** the CI runner architecture differs from the target Lambda architecture
- **THEN** the bundle is still built for the target architecture (via arm64
  runners, a pinned wheel platform, or emulation) — not implicitly for the runner

### Requirement: Cloud Lambdas run on arm64

All cloud-deployed Lambda functions SHALL run on the `arm64` architecture — the
`staging`, `testing`, and `production` environments, across the API, worker,
step-function helpers, and MCP — for cost efficiency and arch uniformity with
local development.

#### Scenario: every cloud environment is arm64
- **WHEN** any cloud environment is deployed
- **THEN** its Lambda functions report the `arm64` architecture

#### Scenario: arch-specific layers follow the function architecture
- **WHEN** a function depends on an architecture-specific layer (e.g. the MCP
  Lambda's AWS Lambda Web Adapter)
- **THEN** the arm64 variant of that layer is selected automatically
