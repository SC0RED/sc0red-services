# Tasks — arm64 Lambda fleet

- [x] 1. Verify aarch64 (manylinux) wheel coverage for the full dependency
  closure. **DONE — PASS:** a native `linux/arm64` `pip install .` (Apple-Silicon
  host, GH_TOKEN for the private dep) resolved clean. All runtime native pkgs
  present as `aarch64-linux-gnu`: `_cffi_backend`, `cryptography`, `curl_cffi`,
  `jiter`, `lxml`, `pydantic_core`, `rpds`, `wrapt`. `signalfield-core` is
  pure-Python (no compiled ext) → builds to a universal wheel, arch-neutral. A
  native arm64 build needs no pinning.
- [ ] 2. Choose & implement the deterministic-bundle approach (design.md): prefer
  arm64 CI runners (`runs-on: ubuntu-24.04-arm`); else pin pip to
  `manylinux2014_aarch64 --only-binary=:all:`; QEMU only if a dep is sdist-only.
- [ ] 3. Flip `lambda_architecture` → `arm64` for `staging` / `testing` /
  `production` in `infrastructure/app.py` (`development` already arm64).
- [ ] 4. Deploy **staging** (dev account). Confirm: Lambdas report `arm64`
  (`aws lambda get-function-configuration --query Architectures`); native imports
  load (no ImportError in logs); a real portfolio scan runs (exercises curl-cffi);
  deployed E2E passes. This is the native-dep gate before anything else.
- [ ] 5. Promote `development → testing`; confirm testing deploy + E2E green.
- [ ] 6. Promote `testing → production`; confirm prod deploy green.
- [ ] 7. Confirm the cost delta (CloudWatch/Cost Explorer) once steady-state.

# Validation

- [ ] V.1 CDK synth/diff clean; `make audit`; no behaviour change.
- [ ] V.2 architecture-reviewer if 3+ infra source files touched; E2E before PR.
- [ ] V.3 branch → PR → await merge authorization; promote per the chain above.
