Run a comprehensive codebase audit checking for quality drift and anti-patterns.

Execute `./scripts/audit.sh` from the project root and report the results. The audit checks:

1. **File size limits** — Backend files over 400 lines, frontend components over 360 lines
2. **Exception handling** — No bare `except Exception` in SQS workers
3. **DynamoDB pagination** — All queries handle `LastEvaluatedKey`
4. **N+1 read patterns** — No `get_by_id()` in loops (use `batch_get`)
5. **Infrastructure guards** — CORS, NEXTAUTH_SECRET, PITR fail-fast for non-dev
6. **Hardcoded secrets** — Dev secrets not in production paths
7. **Cross-file duplication** — No inline tierColors, error handlers, etc.

If the audit finds issues, explain each one and suggest a fix. If all checks pass, confirm the codebase is clean.

After running the script, also manually check:
- Are there any new files that should have tests but don't?
- Are there any new constants that should be in shared locations?
- Has any file grown past the size limits since the last audit?
