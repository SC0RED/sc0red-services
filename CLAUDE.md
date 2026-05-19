# sc0red Advisory (codebase: `janus`) — Claude Code Instructions

## Naming convention: sc0red Advisory (customer) vs. janus (internal)

The customer-facing product is **sc0red Advisory** — that's the brand string on every page, page title, email body, PDF cover, and footer. The underlying codebase is **janus**: the GitHub repo (`SC0RED/janus`), every AWS resource (Lambda, DynamoDB, SQS, IAM roles, log groups, Secrets Manager paths, CloudWatch dashboards), the CDK stack names (`Janus-development`, `Janus-staging`, `Janus-production`), Python / Node package names (`janus-backend`, `janus-frontend`), Docker container names, the local dev DynamoDB table (`janus-dev`), the storage key `localStorage.janus.theme`, and the test fixtures all retain the `janus-*` naming. This is **intentional, not a TODO** — see `openspec/changes/rename-janus-to-sc0red-advisory/` for the full rationale (renaming infra resources would require risky data migrations for zero customer value).

If you're editing customer-visible text (a page, an email template, a PDF component, a brand string in CSS), use **sc0red Advisory**. If you're editing infrastructure, package metadata, or internal symbol names, the `janus-*` family stays.

## MANDATORY: Architecture Review Gate

**Before calling `git commit` on any code change, you MUST run the `architecture-reviewer` agent if ANY of these conditions are true:**

- 3 or more source files were modified
- Changes touch handlers, services, providers, factories, repositories, or pipeline steps
- Method signatures or interfaces were altered

**The architecture reviewer MUST check all of the following:**
1. Standard findings: dead code, unused parameters, fail-fast violations, swallowed exceptions, interface violations
2. **Pattern consistency**: does the new code follow the mandatory codebase patterns below? If a pattern exists for this type of work, the new code MUST use it — not reinvent it.
3. **Prompt externalization**: are any AI prompt strings inline in Python? They must be in `src/pipeline/prompts/`

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

## MANDATORY: Codebase Patterns

Before writing new code, **search the codebase for how similar work is already done**. These patterns are mandatory — not suggestions. Using a different approach (even if it works) creates inconsistency that compounds over time.

### Pipeline Work → `RequestStep` subclass

All AI pipeline work MUST be a `signalfield_core.pipeline.step.RequestStep` subclass, wired into a pipeline factory. Never put AI calls in handlers, standalone scripts, or utility functions.

```python
# Wrong — AI call in a standalone utility function
def validate_companies(companies, ai_factory):
    with ThreadPoolExecutor() as pool:
        results = pool.map(lambda c: ai_factory.get_client().query_structured(...), companies)

# Right — proper pipeline step
class ValidatePortfolioCompanies(RequestStep):
    def __init__(self, ai_client_factory=None):
        super().__init__()
        self._ai_client_factory = ai_client_factory
    def execute(self):
        # Uses FutureManager, run_structured_ai_call, etc.
```

### Parallel AI Calls → `FutureManager` + `run_structured_ai_call`

All parallel AI calls MUST use `signalfield_core.utilities.future_manager.FutureManager` (not `ThreadPoolExecutor`, `asyncio`, or `concurrent.futures` directly). Each individual call MUST go through `src.pipeline.pipeline_steps.ai_call.run_structured_ai_call`.

```python
# Wrong — raw ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=10) as pool:
    futures = [pool.submit(client.query_structured, ...) for c in companies]

# Right — FutureManager + shared AI call function
with FutureManager(name="StepName", max_workers=10) as manager:
    for i, company in enumerate(companies):
        manager.submit_task(self._validate_one, prompt, schema, system_prompt, f"label_{i}")
    results = manager.wait_for_all_and_collect_results()

def _validate_one(self, prompt, schema, system_prompt, label):
    return run_structured_ai_call(
        ai_client_factory=self._ai_client_factory,
        user_prompt=prompt, schema=schema, system_prompt=system_prompt,
        label=label, step_name="StepName",
    )
```

### AI Prompts → External Files

All AI prompt text MUST be in `src/pipeline/prompts/` — never inline in Python code.

| Content | Location | Loaded via |
|---------|----------|-----------|
| System prompts | `prompts/system/{name}.md` | `load_system_prompt(name)` |
| User prompt templates | `prompts/templates/{name}.md` | `load_template(name)` |
| Calibration guides | `prompts/guides/{name}.md` | `load_guide(name)` |
| Output schemas | `prompts/schemas/{name}.json` | `load_schema(name)` |

### HTML Templates → External Files

HTML content (email templates, rendered pages) MUST be in external `.html` files — never inline as Python string constants. Load at module level via `Path.read_text()`.

| Content | Location | Example |
|---------|----------|---------|
| Email templates | `src/handlers/templates/{name}.html` | `invitation_email.html` |

### Handler Functions → Focused Modules

API handlers are standalone functions in focused modules (`auth_handlers.py`, `scan_handlers.py`, `analysis_handlers.py`, `document_handlers.py`). Each receives explicit dependencies — no class state. The main `api_gateway_handler.py` only does routing + dispatch.

### Pipeline Factory Wiring

New pipeline steps are wired through the factory chain: `FactoryManager` → `JanusFactoriesFactory` → `CompanyAnalysisFactory` (or `PortfolioScanFactory`) → step list. Never call pipeline steps directly from handlers.

These patterns exist because inconsistency was the #1 source of bugs in this codebase. Every "quick shortcut" that bypassed these patterns eventually had to be rewritten.

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

## File Size Limits

- **Backend**: No Python file over 400 lines. Split into focused modules at natural boundaries.
- **Frontend**: No component over 360 lines. Extract sub-components.
- If a file exceeds these limits, **split it before adding more code**.
- Enforced by ruff `max-lines=400` for Python. Frontend is a manual check.

These limits exist because two God objects (APIGatewayHandler at 806 lines, AnalysisDetail at 1,065 lines) accumulated incrementally — no single PR was the problem, but no gate flagged the growth.

---

## DynamoDB Patterns (Non-Negotiable)

- Every `query()` call MUST handle pagination via `LastEvaluatedKey` — DynamoDB silently truncates results at 1MB.
- Never call `get_by_id()` in a loop — use `batch_get_item()` for multiple reads. The `DynamoDBTable.batch_get()` and `CompanyRepository.get_by_ids()` methods exist for this.
- Store computed counts on the record at write time (e.g., `completed_count` on scan records) rather than re-counting with queries at read time.

These rules exist because silent pagination bugs and N+1 query patterns were found in production code that passed all tests (tests used small data).

---

## Exception Handling in Workers

SQS/Lambda worker handlers must catch ONLY domain-specific exceptions (`EngineError`, `ValueError`, `RuntimeError`), not bare `Exception`. Programming errors (`AttributeError`, `KeyError`, `TypeError`) must propagate to:
1. Trigger SQS retry via `batchItemFailures`
2. Surface in CloudWatch as stack traces, not silent "analysis failed" messages

```python
# Wrong — hides bugs as user-visible errors
except Exception as error:
    record_failure(str(error))

# Right — only catch expected domain errors
except (EngineError, ValueError, RuntimeError) as error:
    record_failure(str(error))
# Programming errors propagate to SQS retry + CloudWatch
```

---

## Cross-File Duplication

Before defining a constant, color map, interface, or utility function, **search the codebase for existing definitions**. Common shared locations:

| Area | Shared Location |
|------|----------------|
| Backend models/literals | `src/models/model_literals.py` |
| Backend utilities | `src/utilities/` |
| Frontend types | `src/lib/types/api.ts` |
| Frontend risk utilities | `src/lib/utils/riskUtils.ts` |
| Frontend lever colors | `src/lib/utils/leverColors.ts` |
| Frontend API errors | `src/lib/api/routeError.ts` |
| SQS message schemas | `src/handlers/sqs_messages.py` |
| DynamoDB table setup | `scripts/setup_dynamodb.py` |
| Deploy script helpers | `scripts/lib/common.sh` |

If it exists, import it. If it doesn't, put it in the shared location — not inline.

---

## Infrastructure Defaults

Non-development deployments MUST NOT use fallback default values for:
- **CORS origins**: must specify exact `FRONTEND_DOMAIN` (CDK synth fails without it)
- **NEXTAUTH_SECRET**: must be a unique production secret (CDK synth fails without it)
- **PITR**: enabled for production DynamoDB table

These guards are enforced in `infrastructure/stacks/janus_stack.py`. If adding new infrastructure that has security-relevant defaults, add the same pattern: fail-fast at synth for non-development environments.

---

## Codebase Audit

Run `make audit` periodically (or use `/audit` in Claude Code) to check for:
- Files exceeding size limits
- Infrastructure configuration drift
- Common anti-patterns (bare exceptions, .get() on required fields, hardcoded secrets)

The audit also runs automatically in CI on every PR via the `audit` job.

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
