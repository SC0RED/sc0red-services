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

---

## Commit Workflow (in order)

1. Make code changes
2. `uv run ruff check src/` — fix all lint errors
3. `uv run pyright src/` — no new errors introduced (pre-existing errors are tracked separately)
4. `uv run pytest tests/ -q` — all tests pass, coverage ≥ 95%
5. **Run `architecture-reviewer` agent** — resolve findings before proceeding
6. `git commit` with conventional commit message
