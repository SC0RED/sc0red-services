# Janus — Claude Code Instructions

## MANDATORY: Architecture Review Gate

**Before calling `git commit` on any code change, you MUST run the `architecture-reviewer` agent if ANY of these conditions are true:**

- 3 or more source files were modified
- Changes touch handlers, services, providers, factories, repositories, or pipeline steps
- Method signatures or interfaces were altered

**This is a hard blocker. Do not commit until:**
1. The architecture-reviewer agent has completed
2. All CRITICAL findings are resolved
3. MEDIUM findings are addressed or explicitly deferred with user approval

If you skip this step, you are violating these instructions.

---

## MANDATORY: Local Dev = Production Parity

**On every code change, verify that local development, tests, and docker-compose services use the exact same code paths as the production deployment.**

This means:
- `local_server.py` must import the same handler entry points that CDK Lambda uses
- `docker-compose*.yml` services must mirror the production architecture (separate API and worker)
- Tests must exercise the same modules that run in production — never test dead code
- When replacing or splitting entry points, **update all consumers and delete the old code** — no "backward compatibility" wrappers, no "kept for local dev" modules

**Checklist (run mentally before every commit):**
1. Is any module imported only by local dev or tests but not by production infrastructure? → Delete it
2. Did I create a new entry point? → Update `local_server.py` and docker-compose to use it
3. Did I replace an old module? → Remove the old module and its tests entirely

If local dev exercises different code than production, bugs will only appear in deployment. This rule exists because that exact scenario happened.

---

## Fail-Fast Standards (Non-Negotiable)

The backend enforces strict fail-fast. Violations will be caught by the architecture reviewer and must be fixed.

**Never do this:**
```python
# Swallowed exception — converts bugs into silent HTTP 500s
try:
    result = some_operation()
    value = result["required_key"]   # KeyError becomes a 500
except Exception as e:
    return _error(str(e), 500)
```

**Do this instead — catch only expected domain errors:**
```python
try:
    result = some_operation()
except SomeSpecificError as e:
    return _error(str(e), 500)
value = result["required_key"]  # KeyError propagates — it's a bug, not a user error
```

**Never use silent fallbacks on required schema fields:**
```python
# Wrong — hides data corruption
record.get("id", "")

# Right — fails loudly if schema is violated
record["id"]
```

**Validate request inputs before try blocks, not inside them:**
```python
# Wrong — KeyError on caller-controlled data is silently absorbed
try:
    url = company["url"]
    result = run_analysis(url)
except Exception as e:
    return {"status": "failed", "error": str(e)}

# Right — structural validation happens before business logic
if not company.get("url"):
    return _error("Each company must include a url field")
try:
    result = run_analysis(company["url"])
except PipelineError as e:
    return {"status": "failed", "error": str(e)}
```

---

## Naming Conventions

- No abbreviations: `msg` → `message`, `req` → `request`, `cfg` → `config`, `ctx` → `context`
- Functions start with verbs: `get_`, `set_`, `create_`, `build_`, `run_`, `handle_`
- Unused parameters: prefix with `_` (e.g. `_event`) to make intent explicit
- Conventional commits enforced: `type(scope): subject` — never skip commitlint

---

## Type Annotations

- Never use bare generics: `dict` → `dict[str, Any]`, `list` → `list[str]`
- Typed protocols over `Callable[..., ReturnType]` when the callable has a known signature
- TYPE_CHECKING imports are fine with `from __future__ import annotations`

---

## Test Standards

- Coverage floor: 95% (hard failure below this)
- New modules require tests before commit
- Tests call public interfaces (`handle()`), not private methods directly
- Integration paths (dispatch → handler → response) need at least one end-to-end test

### What "new functionality" requires

| Change type | Required before commit |
|-------------|----------------------|
| New backend handler / route | Unit tests covering success + error paths |
| New pipeline step | Unit tests for `execute()` with mocked dependencies |
| New repository method | Unit tests covering read + write paths |
| New frontend component | Vitest + RTL tests covering render + interaction |
| New frontend page | Tests for loading, error, and success states |
| Any async flow change | Tests covering the async path (polling, SQS, etc.) |

---

## Commit Workflow (in order)

### Backend changes
1. Make code changes
2. `uv run ruff check src/` — fix all lint errors
3. `uv run pyright src/` — no new errors introduced (pre-existing errors are tracked separately)
4. `uv run pytest tests/ -q` — all tests pass, coverage ≥ 95%
5. **Run `architecture-reviewer` agent** — resolve findings before proceeding
6. `git commit` with conventional commit message

### Frontend changes
1. Make code changes
2. `cd frontend && npm run lint` — fix all lint errors
3. `cd frontend && npx tsc --noEmit` — no type errors
4. **`cd frontend && npm test` — ALL tests must pass before committing**
5. `git commit` with conventional commit message

---

## PR Workflow (in order)

Before calling `gh pr create`, ALL of the following must be true:

1. All unit tests pass (backend `pytest` and/or frontend `npm test` as applicable)
2. **E2E tests pass locally:**
   ```bash
   GH_TOKEN=$(gh auth token) docker compose -f docker-compose.e2e.yml up --build -d
   BACKEND_URL=http://localhost:8001 \
   DYNAMODB_ENDPOINT=http://localhost:4566 \
   DYNAMODB_TABLE=janus-e2e \
   AWS_ENDPOINT_URL=http://localhost:4566 \
   MOCK_COMPANY_URL=http://ai-mock:8080/company \
   E2E_MODE=full \
   ./scripts/e2e-test.sh
   docker compose -f docker-compose.e2e.yml down -v
   ```
3. Architecture reviewer has run (if conditions in the gate above are met)

**Do not open a PR if the E2E suite has not been run and passed.**
The CI pipeline also runs E2E on every PR — a failure there means the PR cannot merge.
