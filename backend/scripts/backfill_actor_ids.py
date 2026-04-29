"""Backfill Cognito-sub actor ids on stored records to internal user ids.

Why this exists
---------------
Pre-`fix-actor-attribution`, `authentication.user_id` was sourced
from the JWT's `sub` claim when `custom:legacy_user_id` was missing.
Every record that captured an actor (`deleted_by` on tombstoned rows;
`created_by` on scans / companies; `invited_by` on invitations)
therefore stored the Cognito sub instead of the internal user id.
The Recently Deleted UI and the activity feed both look up the
stored value in a `{user["id"]: user}` map keyed on internal id, so
attribution silently falls through to "Unknown" / "Someone".

This script repairs the historical data. It scans every record in
the table that carries one of those three actor fields, translates
any value that matches a known Cognito sub into the corresponding
internal `user["id"]`, and writes the corrected value back.

Idempotent. Saves a JSON diff log per `--apply` run.

Required environment
--------------------
  DYNAMODB_TABLE          full table name (e.g. `janus-production`)
  AWS_REGION / AWS_DEFAULT_REGION  matching the table's region
  AWS_ENDPOINT_URL        set when running against LocalStack

Run from the backend dir
------------------------
  python scripts/backfill_actor_ids.py --org-id ORG --dry-run
  python scripts/backfill_actor_ids.py --org-id ORG --apply

Idempotency
-----------
At script start we pre-build:
  - `set(user["id"] for user in find_by_org(ORG))` — the universe
    of known internal user ids
  - `dict(user["cognito_sub"] -> user["id"])` — the translation map
For each record we then check the actor field:
  - already in the user-id set → leave (no-op)
  - in the sub→id map        → translate
  - neither                  → log as unresolved, leave alone

Per-record decision is O(1) — no inner-loop DynamoDB queries.

Rollback
--------
The `--apply` run saves a JSON diff log to
  out/backfill_actor_ids_${env}_${timestamp}.json
with `{record_pk, record_sk, field, old, new}` entries. To revert,
write a short reverse-translate script that consumes the log and
re-applies the old values via `UpdateItem`. Do not rely on
point-in-time-restore for selective rollback — the rest of the table
changed during the same window.
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

# Match the path-insert pattern from cleanup_orphan_scans.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.dynamodb.provider import DynamoDBStorageProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Fields that store actor ids and may currently carry a Cognito sub.
# `deleted_by`     — soft-delete tombstones (`fix-actor-attribution`
#                    Phase 1, recently shipped)
# `created_by`     — scan records, plus company records once
#                    `fix-actor-attribution` lands
# `invited_by`     — invitation records
ACTOR_FIELDS = ("deleted_by", "created_by", "invited_by")

# Cap on how many unresolved (off-boarded-user) records we log
# verbatim before summarising. Operators don't need the full list to
# decide whether the count looks right.
UNRESOLVED_LOG_LIMIT = 10


def build_translation_map(
    storage: DynamoDBStorageProvider, org_id: str
) -> tuple[set[str], dict[str, str]]:
    """Return (known internal user ids, cognito_sub → internal id map)."""
    user_repo = storage.create_user_repository()
    users = user_repo.find_by_org(org_id)
    user_ids: set[str] = set()
    sub_to_id: dict[str, str] = {}
    for user in users:
        user_id = user.get("id", "")
        if not user_id:
            continue
        user_ids.add(user_id)
        sub = user.get("cognito_sub", "")
        if sub:
            sub_to_id[sub] = user_id
    return user_ids, sub_to_id


def scan_records_for_org(
    storage: DynamoDBStorageProvider, org_id: str
) -> list[dict[str, Any]]:
    """Return every record carrying an actor field for the org.

    Pages through GSI1 (org→record listing) for companies + users +
    invitations, and GSI2 for scans. The cleanup-script code path
    already handles each entity-type read pattern, so we reuse the
    repos rather than reinventing.
    """
    company_repo = storage.create_company_repository()
    scan_repo = storage.create_scan_repository()
    invitation_repo = storage.create_invitation_repository()

    records: list[dict[str, Any]] = []

    # Companies (live + tombstoned via the recovery-aware variants;
    # tombstones are exactly the rows we most need to translate).
    companies, _cursor = company_repo.find_by_org(org_id)
    records.extend(companies)
    records.extend(company_repo.find_tombstoned_by_org(org_id))

    # Scans (same shape: live + tombstoned).
    records.extend(scan_repo.find_recent_by_org(org_id, limit=None))
    records.extend(scan_repo.find_tombstoned_by_org(org_id))

    # Invitations.
    records.extend(invitation_repo.find_by_org(org_id))

    return records


def translate_record(
    record: dict[str, Any],
    user_ids: set[str],
    sub_to_id: dict[str, str],
) -> dict[str, str]:
    """Return `{field: new_value}` for actor fields that need translation.

    Empty dict means "no changes needed" (already-internal id, or no
    actor field at all). `unresolved` values (subs that don't match any
    current user) are NOT translated — caller logs them but leaves the
    record alone.
    """
    updates: dict[str, str] = {}
    for field in ACTOR_FIELDS:
        value = record.get(field, "")
        if not value:
            continue
        if value in user_ids:
            # Already an internal user id — nothing to do.
            continue
        if value in sub_to_id:
            updates[field] = sub_to_id[value]
        # else: unresolved (off-boarded user); leave untouched.
    return updates


def write_translations(
    storage: DynamoDBStorageProvider,
    record: dict[str, Any],
    updates: dict[str, str],
) -> None:
    """Apply translated actor fields via `UpdateItem`."""
    pk = record.get("pk")
    sk = record.get("sk")
    if not pk or not sk:
        logger.warning("record missing pk/sk, skipping: %r", record)
        return
    # Use the public `storage.table` accessor directly — these are
    # scan-spanning writes that don't fit any single repository's
    # surface, so we reach into the shared table abstraction.
    storage.table.update_item(
        pk=pk,
        sk=sk,
        updates=updates,
    )


def write_diff_log(diff: list[dict[str, Any]], env: str) -> Path:
    """Write the planned-or-applied translations to a JSON file."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"backfill_actor_ids_{env}_{timestamp}.json"
    path.write_text(json.dumps(diff, indent=2))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--org-id", required=True, help="Org id to backfill.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write translated values back. Default: dry-run.",
    )
    parser.add_argument(
        "--env",
        default=os.environ.get("DYNAMODB_TABLE", "unknown"),
        help="Environment label for the diff log filename (default: $DYNAMODB_TABLE).",
    )
    args = parser.parse_args()

    storage = DynamoDBStorageProvider()
    user_ids, sub_to_id = build_translation_map(storage, args.org_id)
    logger.info(
        "translation map: %d known user ids, %d sub→id mappings",
        len(user_ids),
        len(sub_to_id),
    )

    records = scan_records_for_org(storage, args.org_id)
    logger.info("scanning %d records for actor-field translations", len(records))

    diff: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for record in records:
        updates = translate_record(record, user_ids, sub_to_id)
        if not updates:
            # Check whether any actor field has an unresolved sub
            # (so we can log them at the end).
            for field in ACTOR_FIELDS:
                value = record.get(field, "")
                if value and value not in user_ids and value not in sub_to_id:
                    unresolved.append(
                        {
                            "pk": record.get("pk"),
                            "sk": record.get("sk"),
                            "field": field,
                            "value": value,
                        }
                    )
            continue
        for field, new_value in updates.items():
            diff.append(
                {
                    "pk": record.get("pk"),
                    "sk": record.get("sk"),
                    "field": field,
                    "old": record.get(field),
                    "new": new_value,
                }
            )
        action = "WOULD TRANSLATE" if not args.apply else "TRANSLATING"
        logger.info(
            "%s pk=%s sk=%s fields=%s",
            action,
            record.get("pk"),
            record.get("sk"),
            list(updates),
        )
        if args.apply:
            write_translations(storage, record, updates)

    diff_path = write_diff_log(diff, args.env)
    logger.info(
        "diff log written: %s (%d translations%s)",
        diff_path,
        len(diff),
        " — APPLIED" if args.apply else " — DRY-RUN",
    )
    if unresolved:
        logger.warning(
            "%d records carry actor values that match neither a known user id "
            "nor a known Cognito sub — likely off-boarded users. Leaving untouched.",
            len(unresolved),
        )
        for entry in unresolved[:UNRESOLVED_LOG_LIMIT]:
            logger.warning("  unresolved: %s", entry)
        if len(unresolved) > UNRESOLVED_LOG_LIMIT:
            logger.warning(
                "  … and %d more (see logs).", len(unresolved) - UNRESOLVED_LOG_LIMIT
            )

    if not args.apply:
        print("\nDry-run mode. Re-run with --apply to write the translations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
