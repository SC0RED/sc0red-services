"""Restore tombstoned assessments orphaned by the buggy admin-restore.

Why this exists
---------------
The Phase 2 admin Recently Deleted UI's Restore action only cleared
the tombstone on the top-level record (company / scan). The delete
cascade tombstones MORE than that — for an analysis delete, the
company AND its assessments both get `deleted_at`. The restore was
only reversing the company side, leaving assessments tombstoned and
filtered out by `find_by_company`'s `filter_live`.

Symptom: a restored analysis renders with `companyName` /
`overallRiskScore` / `riskTier` / `topActions` (from the live
company's metadata) but empty `riskScores` / `opportunities` /
`ebitdaTree` / `valueChain` (from still-tombstoned assessments).

The forward-going fix lives in
`backend/src/handlers/admin_restore.py` (cascade-aware restore).
This script repairs records that were already restored before that
fix shipped — i.e. live companies whose assessments are still
tombstoned. Idempotent. Dry-run by default; saves a JSON diff log on
`--apply`.

How it identifies orphans
-------------------------
For each live company in the requested org, we call
`assessment_repo.find_by_company_with_deleted` and collect the
assessment records where `deleted_at` is set. The only path in the
codebase that sets `deleted_at` on an assessment is the
delete-analysis cascade (verified via grep) — so a tombstoned
assessment whose parent company is LIVE is orphan data from the
restore-cascade bug. We restore each one.

Required environment
--------------------
  DYNAMODB_TABLE          full table name (e.g. `janus-production`)
  AWS_REGION / AWS_DEFAULT_REGION  matching the table's region
  AWS_ENDPOINT_URL        set when running against LocalStack

Run from the backend dir
------------------------
  python scripts/restore_orphaned_assessments.py --org-id ORG --dry-run
  python scripts/restore_orphaned_assessments.py --org-id ORG --apply

Rollback
--------
The `--apply` run saves a JSON diff log to
  out/restore_orphaned_assessments_${env}_${timestamp}.json
with `{company_id, assessment_id, deleted_at, ttl}` per restored
row. To revert, write a short script that consumes the log and
re-tombstones via `assessment_repo.tombstone(assessment_id, ...)`.
Don't rely on point-in-time-restore for selective rollback — the
rest of the table changed during the same window.

Note on the TTL eviction race
-----------------------------
A tombstoned assessment whose `ttl` already passed has been
hard-evicted by DynamoDB. `restore()` uses `require_exists=True`,
which surfaces the eviction as
`ConditionalCheckFailedException`. We catch that here and log it as
`ttl_expired` rather than failing the whole sweep. The user-facing
record (the company) is already live, so a missing assessment is at
worst a single empty card — not a regression in the data model.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

# Match the path-insert pattern from cleanup_orphan_scans.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Cap on how many TTL-evicted entries we log verbatim before
# summarising. Operators don't need the full list to decide whether
# the count looks reasonable.
EVICTED_LOG_LIMIT = 10


def find_orphaned_assessments(
    storage: DynamoDBStorageProvider, org_id: str
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Find tombstoned assessments whose parent company is LIVE.

    Returns `[(company, assessment), ...]` so the caller can log
    company-level context alongside each assessment row.
    """
    company_repo = storage.create_company_repository()
    assessment_repo = storage.create_assessment_repository()

    # `find_by_org` returns LIVE companies only. Tombstoned companies
    # whose assessments are also tombstoned are NOT orphans — that's
    # the coherent post-delete state.
    companies, _cursor = company_repo.find_by_org(org_id)

    orphans: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for company in companies:
        analysis_id = company.get("id", "")
        if not analysis_id:
            continue
        assessments = assessment_repo.find_by_company_with_deleted(analysis_id)
        orphans.extend(
            (company, assessment) for assessment in assessments if assessment.get("deleted_at")
        )
    return orphans


def write_diff_log(diff: list[dict[str, Any]], env: str) -> Path:
    """Persist the planned-or-applied restorations as a JSON file."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"restore_orphaned_assessments_{env}_{timestamp}.json"
    path.write_text(json.dumps(diff, indent=2))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--org-id",
        required=True,
        help="Org id to scan + repair.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Restore the orphaned assessments. Default: dry-run.",
    )
    parser.add_argument(
        "--env",
        default=os.environ.get("DYNAMODB_TABLE", "unknown"),
        help="Environment label for the diff log filename (default: $DYNAMODB_TABLE).",
    )
    args = parser.parse_args()

    storage = DynamoDBStorageProvider()
    assessment_repo = storage.create_assessment_repository()

    orphans = find_orphaned_assessments(storage, args.org_id)
    logger.info("found %d orphaned tombstoned assessments for org %s", len(orphans), args.org_id)

    diff: list[dict[str, Any]] = []
    evicted: list[dict[str, Any]] = []

    for company, assessment in orphans:
        entry = {
            "company_id": company.get("id"),
            "company_name": company.get("company_name", ""),
            "assessment_id": assessment.get("id"),
            "deleted_at": assessment.get("deleted_at"),
            "ttl": assessment.get("ttl"),
        }
        action = "WOULD RESTORE" if not args.apply else "RESTORING"
        logger.info(
            "%s assessment_id=%s company_id=%s deleted_at=%s",
            action,
            entry["assessment_id"],
            entry["company_id"],
            entry["deleted_at"],
        )
        if args.apply:
            try:
                assessment_repo.restore(assessment["id"])
            except ClientError as error:
                code = error.response.get("Error", {}).get("Code", "")
                if code == "ConditionalCheckFailedException":
                    logger.warning(
                        "  ttl_expired assessment_id=%s — already TTL-evicted, skipping",
                        assessment["id"],
                    )
                    evicted.append(entry)
                    continue
                raise
        diff.append(entry)

    diff_path = write_diff_log(diff, args.env)
    logger.info(
        "diff log written: %s (%d restorations%s)",
        diff_path,
        len(diff),
        " — APPLIED" if args.apply else " — DRY-RUN",
    )

    if evicted:
        logger.warning(
            "%d assessments were TTL-evicted before we could restore them — "
            "the underlying rows are gone. Listing the first %d for context:",
            len(evicted),
            min(EVICTED_LOG_LIMIT, len(evicted)),
        )
        for entry in evicted[:EVICTED_LOG_LIMIT]:
            logger.warning("  evicted: %s", entry)
        if len(evicted) > EVICTED_LOG_LIMIT:
            logger.warning("  … and %d more (see logs).", len(evicted) - EVICTED_LOG_LIMIT)

    if not args.apply:
        print("\nDry-run mode. Re-run with --apply to restore the orphaned assessments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
